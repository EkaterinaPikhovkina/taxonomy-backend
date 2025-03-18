import os
import shutil


def delete_pycache(root_dir):
    for root, dirs, files in os.walk(root_dir):
        if "__pycache__" in dirs:
            pycache_dir = os.path.join(root, "__pycache__")
            print(f"Deleting: {pycache_dir}")
            shutil.rmtree(pycache_dir)


if __name__ == "__main__":
    project_root = os.path.dirname(os.path.abspath(__file__))  # Получаем путь к папке, где лежит скрипт
    delete_pycache(project_root)
