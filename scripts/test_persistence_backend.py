from __future__ import annotations

from app.db.persistence_backend import (
    backend_diagnostics,
)


def main() -> None:
    result = backend_diagnostics()

    print("BACKEND =", result["backend"])
    print(
        "DATABASE_URL_CONFIGURED =",
        result["database_url_configured"],
    )
    print(
        "CONNECTION_TESTED =",
        result["connection_tested"],
    )

    if result["backend"] == "postgres":
        print("DATABASE =", result["database"])
        print(
            "DATABASE_USER =",
            result["database_user"],
        )
        print("POSTGRES_CONNECTION=PASS")
    else:
        print("SQLITE_DEFAULT=PASS")


if __name__ == "__main__":
    main()
