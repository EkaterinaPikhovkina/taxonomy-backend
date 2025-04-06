def get_taxonomy_hierarchy_query():
    return """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?class ?subClass
        WHERE {
          ?class a rdfs:Class .
          ?subClass rdfs:subClassOf ?class .
          FILTER (?class != ?subClass)

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
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ex: <http://example.org/taxonomy/>

        DELETE {{
          ?concept ?p ?o .           # Удалить свойства самого концепта
          ?subClass ?sub_p ?sub_o .   # Удалить свойства подклассов
          ?indirectSubClass ?indirect_p ?indirect_o . # Удалить свойства косвенных подклассов
          ?s rdfs:subClassOf ?concept . # Удалить отношения подкласса к удаляемому концепту
          ?s rdfs:subClassOf ?subClass . # Удалить отношения подкласса к прямому подклассу
          ?s rdfs:subClassOf ?indirectSubClass . # Удалить отношения подкласса к косвенному подклассу
        }}
        WHERE {{
          BIND(<{concept_uri}> as ?concept)

          # Найти сам концепт и его свойства
          ?concept ?p ?o .

          # Опционально найти прямые подклассы и их свойства
          OPTIONAL {{
            ?subClass rdfs:subClassOf ?concept .
            ?subClass ?sub_p ?sub_o .
          }}
          # Опционально найти косвенные подклассы (подклассы подклассов) и их свойства.
          # Используем рекурсивный путь rdfs:subClassOf* (ноль или более раз) чтобы найти все уровни подклассов.
          OPTIONAL {{
            ?indirectSubClass rdfs:subClassOf+ ?concept . # + означает 1 или более раз, * - 0 или более
            FILTER (?indirectSubClass != ?concept) # Исключаем сам концепт
            ?indirectSubClass ?indirect_p ?indirect_o .
          }}

          # Опционально найти отношения, где удаляемый концепт или его подклассы являются классом для других подклассов
          OPTIONAL {{ ?s rdfs:subClassOf ?concept . }}
          OPTIONAL {{ ?s rdfs:subClassOf ?subClass . }}
          OPTIONAL {{ ?s rdfs:subClassOf ?indirectSubClass . }}

        }}
    """
