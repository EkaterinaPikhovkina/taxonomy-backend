from fastapi import HTTPException
from SPARQLWrapper import SPARQLWrapper, JSON, TURTLE, RDFXML
import requests

from utils.sparql_queries import (
    clear_repository_query,
    get_taxonomy_hierarchy_query,
    export_taxonomy_query,
    add_subconcept_query,
    add_top_concept_query,
    delete_concept_query,
    update_concept_name_query,
)

GRAPHDB_ENDPOINT_QUERY = "http://localhost:7200/repositories/animals"
GRAPHDB_ENDPOINT_STATEMENTS = "http://localhost:7200/repositories/animals/statements"


def parse_concat_results(concat_string):
    """Parses GROUP_CONCAT results like 'value1|lang1||value2|lang2'."""
    results = []
    if not concat_string or not concat_string.strip():
        return results
    pairs = concat_string.split('||')
    for pair in pairs:
        parts = pair.split('|', 1) # Split only once
        if len(parts) == 2:
            value, lang = parts
            results.append({"value": value, "lang": lang if lang else None})
        elif len(parts) == 1: # Handle case with value but no language tag
             results.append({"value": parts[0], "lang": None})
    # Remove duplicates if necessary (SPARQL GROUP_CONCAT DISTINCT should handle this)
    # unique_results = { (item['value'], item['lang']): item for item in results }.values()
    # return list(unique_results)
    return results


def get_preferred_label(labels_info, preferred_lang="uk"):
    """Gets the preferred language label, falls back to others or URI part."""
    if not labels_info:
        return None
    labels = parse_concat_results(labels_info)
    for label in labels:
        if label["lang"] == preferred_lang:
            return label["value"]
    # Fallback: first available label or None
    return labels[0]["value"] if labels else None


def get_taxonomy_hierarchy():
    sparql = SPARQLWrapper(GRAPHDB_ENDPOINT_QUERY)
    sparql.setQuery(get_taxonomy_hierarchy_query())
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        print("Debug: get_taxonomy_hierarchy - Непосредственный результат из SPARQL query:")
        # print(results)

        return results["results"]["bindings"]
    except Exception as e:
        print(f"Error querying GraphDB: {e}")
        print(f"Query used:\n{get_taxonomy_hierarchy_query()}")  # Print query on error
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к GraphDB: {e}")


def build_hierarchy_tree(bindings):
    nodes = {}
    parent_child_links = {} # Store parent-child URI links { child_uri: parent_uri }
    all_uris = set()

    print("Debug: build_hierarchy_tree - Processing bindings...")

    for binding in bindings:
        class_uri = binding["class"]["value"]
        all_uris.add(class_uri)

        class_labels_info = binding.get("classLabelsInfo", {}).get("value")
        class_comments_info = binding.get("classCommentsInfo", {}).get("value")

        # Use preferred language for title, store all labels/definitions
        preferred_class_label = get_preferred_label(class_labels_info, "uk") or class_uri.split('/')[-1]
        class_definitions = parse_concat_results(class_comments_info)
        all_class_labels = parse_concat_results(class_labels_info) # Store all labels too

        if class_uri not in nodes:
            nodes[class_uri] = {
                "key": class_uri,
                "title": preferred_class_label,
                "children": [],
                "definitions": class_definitions,
                 "labels": all_class_labels # Add labels here
                # "definition": class_definitions[0]['value'] if class_definitions else None # Old single definition
            }
        else: # Update existing node if needed (e.g., if seen as a subclass first)
            nodes[class_uri]["title"] = preferred_class_label
            nodes[class_uri]["definitions"] = class_definitions
            nodes[class_uri]["labels"] = all_class_labels


        if "subClass" in binding and binding["subClass"]["value"]:
            subclass_uri = binding["subClass"]["value"]
            all_uris.add(subclass_uri)
            parent_child_links[subclass_uri] = class_uri # Record link

            subclass_labels_info = binding.get("subClassLabelsInfo", {}).get("value")
            subclass_comments_info = binding.get("subClassCommentsInfo", {}).get("value")

            preferred_subclass_label = get_preferred_label(subclass_labels_info, "uk") or subclass_uri.split('/')[-1]
            subclass_definitions = parse_concat_results(subclass_comments_info)
            all_subclass_labels = parse_concat_results(subclass_labels_info)

            if subclass_uri not in nodes:
                 nodes[subclass_uri] = {
                    "key": subclass_uri,
                    "title": preferred_subclass_label,
                    "children": [],
                    "definitions": subclass_definitions,
                    "labels": all_subclass_labels
                 }
            else: # Update existing node
                nodes[subclass_uri]["title"] = preferred_subclass_label
                nodes[subclass_uri]["definitions"] = subclass_definitions
                nodes[subclass_uri]["labels"] = all_subclass_labels

    # --- Build the tree structure ---
    root_nodes = []
    processed_children = set()

    # Populate children arrays based on recorded links
    for child_uri, parent_uri in parent_child_links.items():
         if parent_uri in nodes and child_uri in nodes:
              # Ensure child is not already added (can happen with complex SPARQL results)
              if nodes[child_uri] not in nodes[parent_uri]["children"]:
                   nodes[parent_uri]["children"].append(nodes[child_uri])
                   processed_children.add(child_uri)
              else:
                   print(f"Debug: Child {child_uri} already in parent {parent_uri}, skipping duplicate add.")
         else:
              print(f"Warning: Parent {parent_uri} or Child {child_uri} not found in nodes dict during linking.")


    # Identify root nodes (those not present as children)
    for uri in all_uris:
        if uri not in parent_child_links: # If a node is never a child, it's a root
            if uri in nodes:
                root_nodes.append(nodes[uri])
            else:
                 print(f"Warning: Potential root node {uri} not found in nodes dictionary.")


    # Handle potential orphans (nodes created but not linked and not identified as roots)
    # This might indicate issues in SPARQL or linking logic
    all_node_uris = set(nodes.keys())
    linked_uris = set(parent_child_links.keys()) | set(parent_child_links.values())
    identified_root_uris = {node['key'] for node in root_nodes}
    orphans = all_node_uris - linked_uris - identified_root_uris
    if orphans:
         print(f"Warning: Found potential orphan nodes (not linked, not root): {orphans}")
         # Decide how to handle orphans, e.g., add them as roots
         # for orphan_uri in orphans:
         #      if orphan_uri in nodes:
         #          root_nodes.append(nodes[orphan_uri])


    print(f"Debug: build_hierarchy_tree - Identified {len(root_nodes)} root nodes.")
    # print("Debug: build_hierarchy_tree - Final tree structure (roots):")
    # print(root_nodes) # Can be very verbose
    return root_nodes


# def build_hierarchy_tree(bindings):
#     nodes = {}
#     root_nodes = []
#     print("Debug: build_hierarchy_tree - Входящие bindings:")
#     print(bindings)
#
#     for binding in bindings:
#         class_uri = binding["class"]["value"]
#         class_label = binding.get("classLabel", {}).get("value")
#         class_comment = binding.get("classComment", {}).get("value")
#
#         print(f"Debug: build_hierarchy_tree - Обработка концепта: class_uri={class_uri}, label={class_label}")
#
#         if class_uri not in nodes:
#             nodes[class_uri] = {
#                 "key": class_uri,
#                 "title": class_label if class_label else class_uri.split('/')[-1],
#                 "children": [],
#                 "definition": class_comment if class_comment else None,
#             }
#
#         print(f"Debug: build_hierarchy_tree - Создан узел: key={nodes[class_uri]['key']}, title={nodes[class_uri]['title']}")
#
#         if "subClass" in binding:
#             subclass_uri = binding["subClass"]["value"]
#             subclass_label = binding.get("subClassLabel", {}).get("value")
#             subclass_comment = binding.get("subClassComment", {}).get("value")
#
#             print(f"Debug: build_hierarchy_tree - Обнаружен подкласс: subclass_uri={subclass_uri}, subclass_label={subclass_label}")
#
#             if subclass_uri not in nodes:
#                 nodes[subclass_uri] = {
#                     "key": subclass_uri,
#                     "title": subclass_label if subclass_label else subclass_uri.split('/')[-1],
#                     "children": [],
#                     "definition": subclass_comment if subclass_comment else None,
#                 }
#
#             print(f"Debug: build_hierarchy_tree - Создан узел подкласса: key={nodes[subclass_uri]['key']}, title={nodes[subclass_uri]['title']}")
#
#             nodes[class_uri]["children"].append(nodes[subclass_uri])
#             print(f"Debug: build_hierarchy_tree - Подкласс добавлен к родителю: parent_uri={class_uri}, child_uri={subclass_uri}")
#         else:
#             root_nodes.append(nodes[class_uri])
#             print(f"Debug: build_hierarchy_tree - Корневой узел добавлен: uri={class_uri}")
#
#     real_root_nodes = []
#     is_subclass = set()
#     for node_uri in nodes:
#         for child in nodes[node_uri]["children"]:
#             is_subclass.add(child["key"])
#
#     for node_uri in nodes:
#         if node_uri not in is_subclass:
#             real_root_nodes.append(nodes[node_uri])
#             print(f"Debug: build_hierarchy_tree - Реальный корневой узел добавлен: uri={node_uri}")
#
#     print("Debug: build_hierarchy_tree - Возвращаемые real_root_nodes:")
#     print(real_root_nodes)
#     return real_root_nodes


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


def import_taxonomy_to_graphdb(file_path, graphdb_endpoint):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        headers = {}

        if file_path.endswith('.ttl'):
            headers['Content-Type'] = 'text/turtle'
        elif file_path.endswith('.rdf'):
            headers['Content-Type'] = 'application/rdf+xml'
        else:
            raise ValueError("Непідтримуваний формат файлу для імпорту")

        response = requests.post(graphdb_endpoint, data=data, headers=headers)

        if response.status_code != 204 and response.status_code != 200:
            raise Exception(
                f"Помилка імпорту в GraphDB. Статус код: {response.status_code}, Відповідь: {response.text}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def export_taxonomy(format_str):
    sparql = SPARQLWrapper(GRAPHDB_ENDPOINT_QUERY)
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


def add_top_concept_to_graphdb(concept_uri, definition, graphdb_endpoint):
    sparql_query = add_top_concept_query(concept_uri, definition)
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


def update_concept_name_in_graphdb(concept_uri, new_concept_name, graphdb_endpoint):
    sparql_query = update_concept_name_query(concept_uri, new_concept_name)
    print("Debug: update_concept_name_in_graphdb - SPARQL Query being sent for update concept name:")
    print("SPARQL Query being sent for update concept name:", sparql_query)

    headers = {'Content-Type': 'application/sparql-update'}
    try:
        response = requests.post(graphdb_endpoint, data=sparql_query, headers=headers)
        print(f"Debug: update_concept_name_in_graphdb - Response from GraphDB:")
        print(f"Debug: update_concept_name_in_graphdb - Status code: {response.status_code}")
        print(
            f"Debug: update_concept_name_in_graphdb - Response content (first 100 chars): {response.content.decode('utf-8')[:100]}")
        if response.status_code != 200 and response.status_code != 204:
            raise Exception(
                f"Помилка при оновленні назви концепту в GraphDB. Статус код: {response.status_code}, Відповідь: {response.text}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка соединения с GraphDB при оновленні назви концепту: {e}")
