def get_taxonomy_hierarchy_query():
    return """
            SELECT
              ?class
              (GROUP_CONCAT(DISTINCT ?classLabelConcat; SEPARATOR="||") AS ?classLabelsInfo)
              (GROUP_CONCAT(DISTINCT ?classCommentConcat; SEPARATOR="||") AS ?classCommentsInfo)
              ?subClass
              (GROUP_CONCAT(DISTINCT ?subClassLabelConcat; SEPARATOR="||") AS ?subClassLabelsInfo)
              (GROUP_CONCAT(DISTINCT ?subClassCommentConcat; SEPARATOR="||") AS ?subClassCommentsInfo)
            WHERE {
              ?class a rdfs:Class .
              FILTER STRSTARTS(STR(?class), "http://example.org/taxonomy/") # Adjust namespace if needed

              # --- Class Labels and Comments ---
              OPTIONAL {
                ?class rdfs:label ?classLabel .
                BIND(CONCAT(STR(?classLabel), "|", LANG(?classLabel)) AS ?classLabelConcat)
              }
              OPTIONAL {
                ?class rdfs:comment ?classComment .
                BIND(CONCAT(STR(?classComment), "|", LANG(?classComment)) AS ?classCommentConcat)
              }

              # --- SubClass Info (Optional) ---
              OPTIONAL {
                ?subClass rdfs:subClassOf ?class .
                FILTER (?class != ?subClass)
                FILTER STRSTARTS(STR(?subClass), "http://example.org/taxonomy/") # Adjust namespace

                OPTIONAL {
                  ?subClass rdfs:label ?subClassLabel .
                  BIND(CONCAT(STR(?subClassLabel), "|", LANG(?subClassLabel)) AS ?subClassLabelConcat)
                }
                OPTIONAL {
                  ?subClass rdfs:comment ?subClassComment .
                  BIND(CONCAT(STR(?subClassComment), "|", LANG(?subClassComment)) AS ?subClassCommentConcat)
                }
              }

              FILTER NOT EXISTS {
                ?intermediateClass rdfs:subClassOf ?class ;
                                   rdfs:subClassOf ?superClass .
                ?subClass rdfs:subClassOf ?intermediateClass .
                FILTER (?intermediateClass != ?class)
                FILTER (?intermediateClass != ?subClass)
              }
            }
            GROUP BY ?class ?subClass # Group to allow GROUP_CONCAT
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
          ?node ?p ?o .                     
          ?s rdfs:subClassOf ?node .       
        }}
        WHERE {{
          BIND(<{concept_uri}> AS ?root)
          ?node rdfs:subClassOf* ?root .
          OPTIONAL {{ ?node ?p ?o . }}
          OPTIONAL {{ ?s rdfs:subClassOf ?node . }}
        }}

    """


def update_concept_name_query(concept_uri, new_concept_name):
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        DELETE {{
          <{concept_uri}> rdfs:label ?oldLabel .
        }}
        INSERT {{
          <{concept_uri}> rdfs:label "{new_concept_name}"@uk .
        }}
        WHERE {{
          OPTIONAL {{ <{concept_uri}> rdfs:label ?oldLabel . FILTER (lang(?oldLabel) = "uk") }}
        }}
    """
