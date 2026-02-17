print("<h1>Seku Chat Backend</h1>")
print("<p>This Python file prints:</p>")
print("<p>Hello, World!</p>")


from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db  # assuming your database.py has this

@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "Database connected successfully!"}
    except Exception as e:
        return {"status": "Error", "detail": str(e)}
