from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse
from utils.graphdb_utils import (
    get_taxonomy_hierarchy,
    build_hierarchy_tree,
    clear_graphdb_repository,
    GRAPHDB_ENDPOINT_STATEMENTS,
    import_taxonomy_to_graphdb,
    export_taxonomy,
    add_top_concept_to_graphdb,
    add_subconcept_to_graphdb,
    delete_concept_from_graphdb,
)
import tempfile
import os
import io
from pydantic import BaseModel

router = APIRouter()


class AddSubConceptRequest(BaseModel):
    concept_name: str
    parent_concept_uri: str


class AddTopConceptRequest(BaseModel):
    concept_name: str
    definition: str = None


class DeleteConceptRequest(BaseModel):
    concept_uri: str


@router.get("/taxonomy-tree")
async def read_taxonomy_tree():
    try:
        bindings = get_taxonomy_hierarchy()

        if not bindings:
            return []
        tree_data = build_hierarchy_tree(bindings)
        print("Результат:")
        print(tree_data)
        return tree_data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Ошибка при обработке запроса: {e}")


@router.post("/clear_repository")
async def clear_repository_endpoint():
    if clear_graphdb_repository(GRAPHDB_ENDPOINT_STATEMENTS):
        return {"message": "Репозиторій успішно очищено"}
    else:
        raise HTTPException(status_code=500, detail="Не вдалося очистити репозиторій")


@router.post("/import_taxonomy")
async def import_taxonomy_endpoint(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith((".ttl", ".rdf")):
            raise HTTPException(status_code=400, detail="Непідтримуваний формат файлу. Використовуйте .ttl або .rdf")

        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp_file:
            contents = await file.read()
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name

        import_taxonomy_to_graphdb(tmp_file_path, GRAPHDB_ENDPOINT_STATEMENTS)  # Передаємо шлях до файлу та endpoint

        os.remove(tmp_file_path)

        return JSONResponse(content={"message": f"Таксономія з файлу '{file.filename}' успішно імпортована"})

    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при імпорті таксономії: {e}")


@router.get("/export_taxonomy")
async def export_taxonomy_endpoint(format: str = Query(..., regex="^(ttl|rdf)$")):
    try:
        content = export_taxonomy(format)

        if format == "ttl":
            content_type = "application/x-turtle"
            filename = "taxonomy.ttl"
        else:
            content_type = "application/rdf+xml"
            filename = "taxonomy.rdf"

        return StreamingResponse(io.BytesIO(content.encode()), media_type=content_type,
                                 headers={"Content-Disposition": f"attachment;filename={filename}"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при експорті таксономії: {e}")


@router.post("/add_topconcept")
async def add_topconcept_endpoint(request: AddTopConceptRequest):
    try:
        concept_name = request.concept_name
        definition = request.definition
        concept_uri = f"http://example.org/taxonomy/{concept_name}"
        print(
            f"Debug: concept_uri={concept_uri}, concept_name={concept_name}, definition={definition}")
        add_top_concept_to_graphdb(concept_uri, definition,
                                     GRAPHDB_ENDPOINT_STATEMENTS)
        return {"message": f"Топ концепт '{concept_name}' успішно додано"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при додаванні топ концепту: {e}")


@router.post("/add_subconcept")
async def add_subconcept_endpoint(request: AddSubConceptRequest):
    try:
        concept_name = request.concept_name
        parent_concept_uri = request.parent_concept_uri
        concept_uri = f"http://example.org/taxonomy/{concept_name}"
        print(f"Debug: concept_uri={concept_uri}, concept_name={concept_name}, parent_concept_uri={parent_concept_uri}")
        add_subconcept_to_graphdb(concept_uri, parent_concept_uri,
                                  GRAPHDB_ENDPOINT_STATEMENTS)
        return {"message": f"Концепт '{concept_name}' успішно додано"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при додаванні концепту: {e}")


@router.post("/delete_concept")
async def delete_concept_endpoint(request: DeleteConceptRequest):
    try:
        concept_uri = request.concept_uri
        delete_concept_from_graphdb(concept_uri, GRAPHDB_ENDPOINT_STATEMENTS)
        return {"message": f"Концепт '{concept_uri}' успішно видалено"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при видаленні концепту: {e}")
