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


def add_top_concept_query(concept_uri):
    return f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ex: <http://example.org/taxonomy/>

        INSERT DATA {{
          <{concept_uri}> rdf:type rdfs:Class .
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


def _escape_sparql_literal_value(value: str) -> str:
    """Escapes double quotes and backslashes for SPARQL literals."""
    if value is None:
        return ""
    # Replace backslashes first, then double quotes
    return value.replace('\\', '\\\\').replace('"', '\\"')


def add_rdfs_label_query(concept_uri, label_value, label_lang):
    escaped_label_value = _escape_sparql_literal_value(label_value)
    if label_lang and label_lang.strip():
        label_triple = f'<{concept_uri}> rdfs:label "{escaped_label_value}"@{label_lang} .'
    else:
        label_triple = f'<{concept_uri}> rdfs:label "{escaped_label_value}" .'

    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          {label_triple}
        }}
    """


def delete_rdfs_label_query(concept_uri, label_value, label_lang):
    escaped_label_value = _escape_sparql_literal_value(label_value)
    if label_lang and label_lang.strip():
        literal_to_delete = f'"{escaped_label_value}"@{label_lang}'
    else:
        literal_to_delete = f'"{escaped_label_value}"'
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        DELETE DATA {{
          <{concept_uri}> rdfs:label {literal_to_delete} .
        }}
    """


def add_rdfs_comment_query(concept_uri, comment_value, comment_lang):
    escaped_comment_value = _escape_sparql_literal_value(comment_value)
    if comment_lang and comment_lang.strip():
        comment_triple = f'<{concept_uri}> rdfs:comment "{escaped_comment_value}"@{comment_lang} .'
    else:
        comment_triple = f'<{concept_uri}> rdfs:comment "{escaped_comment_value}" .'
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        INSERT DATA {{
          {comment_triple}
        }}
    """


def delete_rdfs_comment_query(concept_uri, comment_value, comment_lang):
    escaped_comment_value = _escape_sparql_literal_value(comment_value)
    if comment_lang and comment_lang.strip():
        literal_to_delete = f'"{escaped_comment_value}"@{comment_lang}'
    else:
        literal_to_delete = f'"{escaped_comment_value}"'
    return f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        DELETE DATA {{
          <{concept_uri}> rdfs:comment {literal_to_delete} .
        }}
    """
