from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import mysql.connector
from mysql.connector import Error
import uvicorn
import os

api = FastAPI()
api.mount("/css", StaticFiles(directory="css"), name="css")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname('Csdl_Library'), "html"))
@api.get("/", response_class=HTMLResponse)
async def index(request: Request):
    data = {}
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data'
        )
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES;")
            tables = [table[0] for table in cursor.fetchall()]

            for table_name in tables:
                cursor.execute(f"DESCRIBE {table_name};")
                columns = [column[0] for column in cursor.fetchall()]

                cursor.execute(f"SELECT * FROM {table_name};")
                rows = cursor.fetchall()

                data[table_name] = {
                    "columns": columns,
                    "rows": rows
                }

    except Error as e:
        return HTMLResponse(f" Lỗi kết nối MySQL: {e}")

    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

    return templates.TemplateResponse("data.html", {
        "request": request,
        "data": data
    })

@api.post("/add/{table_name}", status_code=201)
async def add_data(table_name: str, request: Request):
    try:
        # Lấy dữ liệu JSON từ request mà frontend gửi lên
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")

        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data'
        )
        if conn.is_connected():
            cursor = conn.cursor()
            
            # Lấy tên các cột từ keys của JSON
            columns = ", ".join(data.keys())
            # Tạo các placeholder (%s) cho giá trị
            placeholders = ", ".join(["%s"] * len(data))
            
            # Câu lệnh SQL động
            sql_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            # Lấy các giá trị từ values của JSON
            values = tuple(data.values())
            
            # Thực thi câu lệnh với tham số để tránh SQL Injection
            cursor.execute(sql_query, values)
            
            # Commit để lưu thay đổi vào database
            conn.commit()
            
            return {"message": f"Data successfully added to {table_name}", "data": data}

    except Error as e:
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# === THÊM ENDPOINT MỚI ĐỂ XỬ LÝ VIỆC XÓA DỮ LIỆU ===
@api.delete("/delete/{table_name}/{primary_key_column}/{row_id}")
async def delete_data(table_name: str, primary_key_column: str, row_id: str):
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data'
        )
        if conn.is_connected():
            cursor = conn.cursor()
            
            # nhưng giá trị row_id phải được truyền qua tham số để tránh SQL Injection.
            sql_query = f"DELETE FROM {table_name} WHERE {primary_key_column} = %s"
            
            # Thực thi câu lệnh
            cursor.execute(sql_query, (row_id,))
            
            # Commit để lưu thay đổi
            conn.commit()

            # Kiểm tra xem có hàng nào đã được xóa chưa
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Row not found or already deleted")
            
            return {"message": f"Row {row_id} from table {table_name} deleted successfully."}

    except Error as e:
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
# data.py

# ... (giữ nguyên code từ đầu đến hết hàm delete_data)

@api.put("/update/{table_name}/{primary_key_column}/{row_id}")
async def update_data(table_name: str, primary_key_column: str, row_id: str, request: Request):
    try:
        # Lấy dữ liệu JSON từ request body
        data = await request.json()
        if not data:
            raise HTTPException(status_code=400, detail="No data provided for update")

        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data'
        )
        if conn.is_connected():
            cursor = conn.cursor()

            # Chuẩn bị cho câu lệnh UPDATE
            # Ví dụ: SET column1 = %s, column2 = %s
            update_fields = ", ".join([f"{key} = %s" for key in data.keys()])

            # Câu lệnh SQL động để cập nhật
            sql_query = f"UPDATE {table_name} SET {update_fields} WHERE {primary_key_column} = %s"

            # Chuẩn bị các giá trị, bao gồm cả row_id cho mệnh đề WHERE
            values = tuple(data.values()) + (row_id,)

            # Thực thi câu lệnh
            cursor.execute(sql_query, values)
            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Row not found")

            return {"message": "Data updated successfully", "data": data}

    except Error as e:
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def main():
    uvicorn.run("data:api", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
