from database.models import init_db
from importers.loader import run

if __name__ == "__main__":
    init_db()
    run()
