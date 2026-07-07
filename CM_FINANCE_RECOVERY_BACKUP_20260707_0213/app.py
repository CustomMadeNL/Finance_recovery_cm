from database.models import init_db
from importers.loader import run as import_sync

def main():
    print("CM FINANCE RECOVERY v1.0")
    print("=========================")

    print("1. Database init")
    init_db()

    print("2. Import sync data")
    import_sync()

    print("KLAAR")

if __name__ == "__main__":
    main()
