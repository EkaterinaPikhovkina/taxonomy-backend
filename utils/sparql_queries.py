def get_taxonomy_hierarchy_query():
    return """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?class ?subClass
        WHERE {
          ?class a rdfs:Class .
          OPTIONAL { ?subClass rdfs:subClassOf ?class . FILTER (?class != ?subClass) }
          
          FILTER STRSTARTS(STR(?class), "http://example.org/taxonomy/")
          
          FILTER NOT EXISTS {
            ?intermediateClass rdfs:subClassOf ?class ;
                               rdfs:subClassOf ?superClass .
            ?subClass rdfs:subClassOf ?intermediateClass .
            FILTER (?intermediateClass != ?class)
            FILTER (?intermediateClass != ?subClass)
          }
          
        }
        ORDER BY ?class ?subClass
    """


def clear_repository_query():
    return """
        CLEAR ALL
    """


def export_taxonomy_query():
    return """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ex: <http://example.org/taxonomy/>

        CONSTRUCT {
          ?s ?p ?o .
        }
        WHERE {
          ?s ?p ?o .
        }
    """


def add_top_concept_query(concept_uri, definition):
    definition_statement = ""
    if definition:
        definition_statement = f"""<{concept_uri}> rdfs:comment "{definition}" ."""

    return f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ex: <http://example.org/taxonomy/>

        INSERT DATA {{
          <{concept_uri}> rdf:type rdfs:Class .
          {definition_statement}
        }}
    """


def add_subconcept_query(concept_uri, parent_uri):
    return f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ex: <http://example.org/taxonomy/>

        INSERT DATA {{
          <{concept_uri}> rdf:type rdfs:Class .
          <{concept_uri}> rdfs:subClassOf <{parent_uri}> .
        }}
    """


def delete_concept_query(concept_uri):
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        DELETE {{
          ?node ?p ?o .                      # Удаляем все свойства концепта и его подклассов
          ?s rdfs:subClassOf ?node .        # Удаляем подчинённые связи (кто указывает на ?node как на суперкласс)
        }}
        WHERE {{
          BIND(<{concept_uri}> AS ?root)
        
          # Находим сам узел и всех его наследников по иерархии
          ?node rdfs:subClassOf* ?root .
        
          # Удаляем их свойства
          OPTIONAL {{ ?node ?p ?o . }}
        
          # Удаляем связи, где другие классы указывают на них как на суперкласс
          OPTIONAL {{ ?s rdfs:subClassOf ?node . }}
        }}

    """
