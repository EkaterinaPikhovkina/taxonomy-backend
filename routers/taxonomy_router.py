from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import JSONResponse, StreamingResponse
from utils.graphdb_utils import (
    get_taxonomy_hierarchy,
    build_hierarchy_tree,
    clear_graphdb_repository,
    GRAPHDB_ENDPOINT_STATEMENTS,
    import_taxonomy_to_graphdb,
    export_taxonomy,
    add_concept_to_graphdb,
    delete_concept_from_graphdb,
)
import tempfile
import os
import io
from pydantic import BaseModel

router = APIRouter()


class AddConceptRequest(BaseModel):
    concept_name: str
    parent_concept_uri: str


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
                            detail=f"Ошибка при обработке запроса: {e}")  # Возвращаем 500 ошибку клиенту


@router.post("/clear_repository")
async def clear_repository_endpoint():
    if clear_graphdb_repository(GRAPHDB_ENDPOINT_STATEMENTS):
        return {"message": "Репозиторій успішно очищено"}
    else:
        raise HTTPException(status_code=500, detail="Не вдалося очистити репозиторій")


@router.post("/import_taxonomy")
async def import_taxonomy_endpoint(file: UploadFile = File(...)):
    try:
        # Перевірка розширення файлу (можна додати більш детальну перевірку вмісту)
        if not file.filename.endswith((".ttl", ".rdf")):
            raise HTTPException(status_code=400, detail="Непідтримуваний формат файлу. Використовуйте .ttl або .rdf")

        # Зберігаємо файл тимчасово
        with tempfile.NamedTemporaryFile(delete=False, suffix=file.filename) as tmp_file:
            contents = await file.read()  # Зчитуємо вміст файлу
            tmp_file.write(contents)  # Записуємо у тимчасовий файл
            tmp_file_path = tmp_file.name  # Отримуємо шлях до тимчасового файлу

        # Викликаємо функцію для імпорту в GraphDB (цю функцію треба реалізувати в graphdb_utils.py)
        import_taxonomy_to_graphdb(tmp_file_path, GRAPHDB_ENDPOINT_STATEMENTS)  # Передаємо шлях до файлу та endpoint

        # Видаляємо тимчасовий файл
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

        # Використовуємо StreamingResponse для ефективної передачі даних
        return StreamingResponse(io.BytesIO(content.encode()), media_type=content_type,
                                 headers={"Content-Disposition": f"attachment;filename={filename}"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка при експорті таксономії: {e}")


@router.post("/add_concept")
async def add_concept_endpoint(request: AddConceptRequest):
    try:
        concept_name = request.concept_name
        parent_concept_uri = request.parent_concept_uri
        concept_uri = f"http://example.org/taxonomy/{concept_name}" # Simple URI creation, consider better approach in production
        add_concept_to_graphdb(concept_uri, concept_name, concept_name, parent_concept_uri, GRAPHDB_ENDPOINT_STATEMENTS)
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