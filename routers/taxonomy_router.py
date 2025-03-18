from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from utils.graphdb_utils import (
    get_taxonomy_hierarchy,
    build_hierarchy_tree,
    clear_graphdb_repository,
    GRAPHDB_ENDPOINT_STATEMENTS,
    import_taxonomy_to_graphdb
)
import tempfile
import os

router = APIRouter()


@router.get("/taxonomy-tree")
async def read_taxonomy_tree():
    """Эндпоинт для получения иерархии таксономии в виде древовидной структуры."""
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
    """
    Endpoint для очищення GraphDB репозиторію.
    """
    if clear_graphdb_repository(GRAPHDB_ENDPOINT_STATEMENTS):
        return {"message": "Репозиторій успішно очищено"}
    else:
        raise HTTPException(status_code=500, detail="Не вдалося очистити репозиторій")


@router.post("/import_taxonomy")
async def import_taxonomy_endpoint(file: UploadFile = File(...)):
    """
    Endpoint для імпорту таксономії з файлу (.ttl або .rdf).
    """
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
