from typing import Optional

from fastapi import HTTPException
from SPARQLWrapper import SPARQLWrapper, JSON, TURTLE
import requests
import os
from dotenv import load_dotenv
import logging
from urllib.parse import urlparse

from utils.sparql_queries import (
    clear_repository_query,
    get_taxonomy_hierarchy_query,
    export_taxonomy_query,
    add_subconcept_query,
    add_top_concept_query,
    delete_concept_query, add_rdfs_label_query, delete_rdfs_label_query, add_rdfs_comment_query,
    delete_rdfs_comment_query,
    # update_concept_name_query,
)

load_dotenv()
logger = logging.getLogger(__name__)

GRAPHDB_BASE_URL = os.getenv("GRAPHDB_BASE_URL", "http://localhost:7200")
GRAPHDB_REPOSITORY = os.getenv("GRAPHDB_REPOSITORY", "animals")

GRAPHDB_QUERY_ENDPOINT = os.getenv("GRAPHDB_ENDPOINT_QUERY", f"{GRAPHDB_BASE_URL}/repositories/{GRAPHDB_REPOSITORY}")
GRAPHDB_STATEMENTS_ENDPOINT = (
    os.getenv("GRAPHDB_ENDPOINT_STATEMENTS", f"{GRAPHDB_BASE_URL}/repositories/{GRAPHDB_REPOSITORY}/statements"))
DEFAULT_GRAPH_URI = os.getenv("GRAPHDB_DEFAULT_GRAPH", "http://example.org/graph/taxonomy")


def parse_concat_results(concat_string):
    """Parses GROUP_CONCAT results like 'value1|lang1||value2|lang2'."""
    results = []
    if not concat_string or not concat_string.strip():
        return results
    pairs = concat_string.split('||')
    for pair in pairs:
        parts = pair.split('|', 1)
        if len(parts) == 2:
            value, lang = parts
            results.append({"value": value, "lang": lang if lang else None})
        elif len(parts) == 1:
            results.append({"value": parts[0], "lang": None})
    return results


def get_uri_display_name(uri_string: str) -> str:
    if not uri_string:
        return ""
    try:
        parsed_uri = urlparse(uri_string)
        if parsed_uri.fragment:
            return parsed_uri.fragment

        path = parsed_uri.path.strip('/')
        if path:
            return path.split('/')[-1]

        # Fallback for URNs or pathless URIs after host
        if parsed_uri.netloc and not path and not parsed_uri.fragment:  # e.g. http://example.com
            # could use netloc, or decide this is not a good display name
            pass  # Let it fall to raw string split

    except ValueError:  # If URI is malformed and urlparse fails
        pass  # Fall through to simple string manipulation

    # Fallback for non-standard URIs or if parsing didn't yield a good segment
    parts = uri_string.split('/')
    last_part = parts[-1]
    if last_part:
        return last_part
    if len(parts) > 1 and parts[-2]:  # Handle trailing slash
        return parts[-2]
    return uri_string  # Absolute fallback


def get_taxonomy_hierarchy():
    sparql = SPARQLWrapper(GRAPHDB_QUERY_ENDPOINT)
    sparql.setQuery(get_taxonomy_hierarchy_query())
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        print("Debug: get_taxonomy_hierarchy - Непосредственный результат из SPARQL query:")
        # print(results)

        return results["results"]["bindings"]
    except Exception as e:
        print(f"Error querying GraphDB: {e}")
        print(f"Query used:\n{get_taxonomy_hierarchy_query()}")
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к GraphDB: {e}")


def build_hierarchy_tree(bindings):
    nodes = {}
    parent_child_links = {}
    all_uris = set()

    print("Debug: build_hierarchy_tree - Processing bindings...")

    for binding in bindings:
        class_uri = binding["class"]["value"]
        all_uris.add(class_uri)

        class_labels_info = binding.get("classLabelsInfo", {}).get("value")
        class_comments_info = binding.get("classCommentsInfo", {}).get("value")

        # preferred_class_label = get_preferred_label(class_labels_info, "uk") or class_uri.split('/')[-1]
        class_definitions = parse_concat_results(class_comments_info)
        all_class_labels = parse_concat_results(class_labels_info)
        class_title = get_uri_display_name(class_uri)

        if class_uri not in nodes:
            nodes[class_uri] = {
                "key": class_uri,
                "title": class_title,
                "children": [],
                "definitions": class_definitions,
                "labels": all_class_labels
            }
        else:
            nodes[class_uri]["title"] = class_title
            nodes[class_uri]["definitions"] = class_definitions
            nodes[class_uri]["labels"] = all_class_labels

        if "subClass" in binding and binding["subClass"]["value"]:
            subclass_uri = binding["subClass"]["value"]
            all_uris.add(subclass_uri)
            parent_child_links[subclass_uri] = class_uri

            subclass_labels_info = binding.get("subClassLabelsInfo", {}).get("value")
            subclass_comments_info = binding.get("subClassCommentsInfo", {}).get("value")

            # preferred_subclass_label = get_preferred_label(subclass_labels_info, "uk") or subclass_uri.split('/')[-1]
            subclass_definitions = parse_concat_results(subclass_comments_info)
            all_subclass_labels = parse_concat_results(subclass_labels_info)
            subclass_title = get_uri_display_name(subclass_uri)

            if subclass_uri not in nodes:
                nodes[subclass_uri] = {
                    "key": subclass_uri,
                    "title": subclass_title,
                    "children": [],
                    "definitions": subclass_definitions,
                    "labels": all_subclass_labels
                }
            else:
                nodes[subclass_uri]["title"] = subclass_title
                nodes[subclass_uri]["definitions"] = subclass_definitions
                nodes[subclass_uri]["labels"] = all_subclass_labels

    # --- Build the tree structure ---
    root_nodes = []
    processed_children = set()

    # Populate children arrays based on recorded links
    for child_uri, parent_uri in parent_child_links.items():
        if parent_uri in nodes and child_uri in nodes:
            if nodes[child_uri] not in nodes[parent_uri]["children"]:
                nodes[parent_uri]["children"].append(nodes[child_uri])
                processed_children.add(child_uri)
            else:
                print(f"Debug: Child {child_uri} already in parent {parent_uri}, skipping duplicate add.")
        else:
            print(f"Warning: Parent {parent_uri} or Child {child_uri} not found in nodes dict during linking.")

    for uri in all_uris:
        if uri not in parent_child_links:
            if uri in nodes:
                root_nodes.append(nodes[uri])
            else:
                print(f"Warning: Potential root node {uri} not found in nodes dictionary.")

    all_node_uris = set(nodes.keys())
    linked_uris = set(parent_child_links.keys()) | set(parent_child_links.values())
    identified_root_uris = {node['key'] for node in root_nodes}
    orphans = all_node_uris - linked_uris - identified_root_uris
    if orphans:
        print(f"Warning: Found potential orphan nodes (not linked, not root): {orphans}")
        # for orphan_uri in orphans:
        #      if orphan_uri in nodes:
        #          root_nodes.append(nodes[orphan_uri])

    print(f"Debug: build_hierarchy_tree - Identified {len(root_nodes)} root nodes.")
    # print("Debug: build_hierarchy_tree - Final tree structure (roots):")
    # print(root_nodes)
    return root_nodes


def clear_graphdb_repository(graphdb_endpoint):
    clear_query = clear_repository_query()
    print("SPARQL Query being sent (in POST body):", clear_query)

    headers = {'Content-Type': 'application/sparql-update'}

    try:
        response = requests.post(graphdb_endpoint, data=clear_query,
                                 headers=headers)

        if response.status_code == 200 or response.status_code == 204:
            print("Репозиторий GraphDB успешно очищен (requests, POST body)")
            return True
        else:
            print(f"Ошибка при очистке GraphDB репозитория (requests, POST body). Статус код: {response.status_code}")
            print(f"Содержимое ответа: {response.content.decode('utf-8')}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"Ошибка соединения с GraphDB (requests, POST body): {e}")
        return False


def import_taxonomy_to_graphdb(file_path, graphdb_endpoint_statements, file_content_bytes=None, content_type=None):
    logger.info(f"Importing taxonomy to GraphDB endpoint: {graphdb_endpoint_statements}, graph: <{DEFAULT_GRAPH_URI}>")
    headers = {}
    data_to_send = None

    if file_content_bytes and content_type:
        data_to_send = file_content_bytes
        headers['Content-Type'] = content_type
        logger.debug(f"Importing from byte content, type: {content_type}")
    elif file_path:
        logger.debug(f"Importing from file: {file_path}")
        with open(file_path, 'rb') as f:
            data_to_send = f.read()
        if file_path.endswith('.ttl'):
            headers['Content-Type'] = 'text/turtle'
        else:
            raise ValueError("Непідтримуваний формат файлу для імпорту (тільки .ttl)")
    else:
        raise ValueError("Необхідно вказати або шлях до файлу, або вміст файлу для імпорту.")

    params = {'context': f'<{DEFAULT_GRAPH_URI}>'}

    try:
        response = requests.post(graphdb_endpoint_statements, data=data_to_send, headers=headers, params=params)
        response.raise_for_status()
        logger.info(f"Taxonomy imported successfully to GraphDB (status {response.status_code}).")
    except requests.exceptions.RequestException as e:
        error_detail = f"Помилка імпорту в GraphDB: {e}. Статус: {e.response.status_code if 'response' in locals() else 'N/A'}. Відповідь: {response.text if 'response' in locals() and e.response.text else 'N/A'}"
        logger.error(error_detail, exc_info=True)
        raise HTTPException(status_code=500, detail=error_detail)


def export_taxonomy(format_str):
    sparql = SPARQLWrapper(GRAPHDB_QUERY_ENDPOINT)
    sparql.setQuery(export_taxonomy_query())

    if format_str == "ttl":
        sparql.setReturnFormat(TURTLE)
    else:
        raise ValueError("Непідтримуваний формат експорту")

    try:
        results = sparql.queryAndConvert()
        return results.decode()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при експорті з GraphDB: {e}")


def add_top_concept_to_graphdb(concept_uri, graphdb_endpoint):
    sparql_query = add_top_concept_query(concept_uri)
    print("SPARQL Query being sent for add top concept:", sparql_query)

    headers = {'Content-Type': 'application/sparql-update'}
    try:
        response = requests.post(graphdb_endpoint, data=sparql_query, headers=headers)
        if response.status_code != 200 and response.status_code != 204:
            raise Exception(
                f"Помилка при додаванні топ концепту в GraphDB. Статус код: {response.status_code}, Відповідь: {response.text}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка соединения с GraphDB при добавлении топ концепта: {e}")


def add_subconcept_to_graphdb(concept_uri, parent_concept_uri, graphdb_endpoint):
    sparql_query = add_subconcept_query(concept_uri, parent_concept_uri)
    print("SPARQL Query being sent for add concept:", sparql_query)

    headers = {'Content-Type': 'application/sparql-update'}
    try:
        response = requests.post(graphdb_endpoint, data=sparql_query, headers=headers)
        if response.status_code != 200 and response.status_code != 204:
            raise Exception(
                f"Помилка при додаванні концепту в GraphDB. Статус код: {response.status_code}, Відповідь: {response.text}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка соединения с GraphDB при добавлении концепта: {e}")


def delete_concept_from_graphdb(concept_uri, graphdb_endpoint):
    sparql_query = delete_concept_query(concept_uri)
    print("SPARQL Query being sent for delete concept:", sparql_query)

    headers = {'Content-Type': 'application/sparql-update'}
    try:
        response = requests.post(graphdb_endpoint, data=sparql_query, headers=headers)
        if response.status_code != 200 and response.status_code != 204:
            raise Exception(
                f"Помилка при видаленні концепту з GraphDB. Статус код: {response.status_code}, Відповідь: {response.text}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка соединения с GraphDB при удалении концепта: {e}")


def _execute_sparql_update(query: str, graphdb_endpoint: str, operation_description: str):
    """Helper function to execute SPARQL update queries."""
    logger.debug(f"SPARQL Update Query for {operation_description}:\n{query}")
    headers = {'Content-Type': 'application/sparql-update'}
    try:
        response = requests.post(graphdb_endpoint, data=query, headers=headers)
        # GraphDB typically returns 204 No Content for successful updates
        if response.status_code == 200 or response.status_code == 204:
             logger.info(f"{operation_description} successful. Status: {response.status_code}")
             return True
        else:
            response.raise_for_status() # Raise HTTPError for other error codes
    except requests.exceptions.HTTPError as http_err:
        error_detail = (f"HTTP error during {operation_description}: {http_err}. "
                        f"Status: {http_err.response.status_code}. Response: {http_err.response.text}")
        logger.error(error_detail)
        raise HTTPException(status_code=http_err.response.status_code, detail=error_detail)
    except requests.exceptions.RequestException as e:
        error_detail = f"Connection error during {operation_description} with GraphDB: {e}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
    return False # Should not be reached if an exception is raised


def add_rdfs_label_to_graphdb(concept_uri: str, label_value: str, label_lang: Optional[str], graphdb_endpoint: str):
    sparql_query = add_rdfs_label_query(concept_uri, label_value, label_lang)
    _execute_sparql_update(sparql_query, graphdb_endpoint, f"adding rdfs:label '{label_value}@{label_lang if label_lang else ''}' to <{concept_uri}>")


def delete_rdfs_label_from_graphdb(concept_uri: str, label_value: str, label_lang: Optional[str], graphdb_endpoint: str):
    sparql_query = delete_rdfs_label_query(concept_uri, label_value, label_lang)
    _execute_sparql_update(sparql_query, graphdb_endpoint, f"deleting rdfs:label '{label_value}@{label_lang if label_lang else ''}' from <{concept_uri}>")


def add_rdfs_comment_to_graphdb(concept_uri: str, comment_value: str, comment_lang: Optional[str], graphdb_endpoint: str):
    sparql_query = add_rdfs_comment_query(concept_uri, comment_value, comment_lang)
    _execute_sparql_update(sparql_query, graphdb_endpoint, f"adding rdfs:comment to <{concept_uri}>")


def delete_rdfs_comment_from_graphdb(concept_uri: str, comment_value: str, comment_lang: Optional[str], graphdb_endpoint: str):
    sparql_query = delete_rdfs_comment_query(concept_uri, comment_value, comment_lang)
    _execute_sparql_update(sparql_query, graphdb_endpoint, f"deleting rdfs:comment from <{concept_uri}>")