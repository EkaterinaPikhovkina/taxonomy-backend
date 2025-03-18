def get_taxonomy_hierarchy_query():
    """
    SPARQL запит для отримання ієрархії таксономії.
    """
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
    """
    SPARQL запит для видалення всіх тріплетів з репозиторію.
    """
    return """
        CLEAR ALL
    """
