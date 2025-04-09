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


def get_taxonomy_hierarchy():
    sparql = SPARQLWrapper(GRAPHDB_ENDPOINT_QUERY)
    sparql.setQuery(get_taxonomy_hierarchy_query())
    sparql.setReturnFormat(JSON)

    try:
        results = sparql.query().convert()
        print("Debug: get_taxonomy_hierarchy - Непосредственный результат из SPARQL query:")
        print(results)

        return results["results"]["bindings"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к GraphDB: {e}")

def build_hierarchy_tree(bindings):
    nodes = {}
    root_nodes = []
    print("Debug: build_hierarchy_tree - Входящие bindings:")
    print(bindings)

    for binding in bindings:
        class_uri = binding["class"]["value"]
        class_label = binding.get("classLabel", {}).get("value")
        class_comment = binding.get("classComment", {}).get("value")

        print(f"Debug: build_hierarchy_tree - Обработка концепта: class_uri={class_uri}, label={class_label}")

        if class_uri not in nodes:
            nodes[class_uri] = {
                "key": class_uri,
                "title": class_label if class_label else class_uri.split('/')[-1],
                "children": [],
                "definition": class_comment if class_comment else None,
            }

        print(f"Debug: build_hierarchy_tree - Создан узел: key={nodes[class_uri]['key']}, title={nodes[class_uri]['title']}")

        if "subClass" in binding:
            subclass_uri = binding["subClass"]["value"]
            subclass_label = binding.get("subClassLabel", {}).get("value")
            subclass_comment = binding.get("subClassComment", {}).get("value")

            print(f"Debug: build_hierarchy_tree - Обнаружен подкласс: subclass_uri={subclass_uri}, subclass_label={subclass_label}")

            if subclass_uri not in nodes:
                nodes[subclass_uri] = {
                    "key": subclass_uri,
                    "title": subclass_label if subclass_label else subclass_uri.split('/')[-1],
                    "children": [],
                    "definition": subclass_comment if subclass_comment else None,
                }

            print(f"Debug: build_hierarchy_tree - Создан узел подкласса: key={nodes[subclass_uri]['key']}, title={nodes[subclass_uri]['title']}")

            nodes[class_uri]["children"].append(nodes[subclass_uri])
            print(f"Debug: build_hierarchy_tree - Подкласс добавлен к родителю: parent_uri={class_uri}, child_uri={subclass_uri}")
        else:
            root_nodes.append(nodes[class_uri])
            print(f"Debug: build_hierarchy_tree - Корневой узел добавлен: uri={class_uri}")

    real_root_nodes = []
    is_subclass = set()
    for node_uri in nodes:
        for child in nodes[node_uri]["children"]:
            is_subclass.add(child["key"])

    for node_uri in nodes:
        if node_uri not in is_subclass:
            real_root_nodes.append(nodes[node_uri])
            print(f"Debug: build_hierarchy_tree - Реальный корневой узел добавлен: uri={node_uri}")

    print("Debug: build_hierarchy_tree - Возвращаемые real_root_nodes:")
    print(real_root_nodes)
    return real_root_nodes


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
