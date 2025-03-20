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
