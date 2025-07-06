from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import mysql.connector
from mysql.connector import Error
import uvicorn
import os
from datetime import date, datetime

api = FastAPI()
api.mount("/css", StaticFiles(directory="css"), name="css")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname('Csdl_Library'), "html"))

@api.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # ... (Hàm này không thay đổi)
    data = {}
    conn = None
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
            
            merged_tables = ['sdt_thu_thu', 'sdt_ban_doc']

            for table_name in tables:
                if table_name in merged_tables:
                    continue

                columns = []
                rows = []

                if table_name == 'thu_thu':
                    sql_query = """
                        SELECT 
                            tt.ma_thu_thu, 
                            tt.ho_va_ten, 
                            tt.trang_thai, 
                            GROUP_CONCAT(sdt.so_dien_thoai SEPARATOR ', ') as so_dien_thoai
                        FROM thu_thu tt
                        LEFT JOIN sdt_thu_thu sdt ON tt.ma_thu_thu = sdt.ma_thu_thu
                        GROUP BY tt.ma_thu_thu, tt.ho_va_ten, tt.trang_thai;
                    """
                    cursor.execute(sql_query)
                    columns = [i[0] for i in cursor.description]
                    rows = cursor.fetchall()

                elif table_name == 'ban_doc':
                    sql_query = """
                        SELECT 
                            bd.ma_ban_doc, 
                            bd.ho_va_ten, 
                            bd.ngay_sinh, 
                            bd.trang_thai, 
                            bd.gioi_tinh, 
                            GROUP_CONCAT(sdt.so_dien_thoai SEPARATOR ', ') as so_dien_thoai
                        FROM ban_doc bd
                        LEFT JOIN sdt_ban_doc sdt ON bd.ma_ban_doc = sdt.ma_ban_doc
                        GROUP BY bd.ma_ban_doc, bd.ho_va_ten, bd.ngay_sinh, bd.trang_thai, bd.gioi_tinh;
                    """
                    cursor.execute(sql_query)
                    columns = [i[0] for i in cursor.description]
                    rows = cursor.fetchall()

                else:
                    cursor.execute(f"DESCRIBE {table_name};")
                    columns = [column[0] for column in cursor.fetchall()]
                    cursor.execute(f"SELECT * FROM {table_name};")
                    rows = cursor.fetchall()
                
                processed_rows = []
                for row in rows:
                    processed_row = tuple(
                        cell.isoformat() if isinstance(cell, (date, datetime)) else cell
                        for cell in row
                    )
                    processed_rows.append(processed_row)

                data[table_name] = {
                    "columns": columns,
                    "rows": processed_rows
                }

    except Error as e:
        return HTMLResponse(f" Lỗi kết nối MySQL: {e}")

    finally:
        if conn and conn.is_connected():
            conn.close()

    return templates.TemplateResponse("data.html", {
        "request": request,
        "data": data
    })


@api.post("/add/{table_name}", status_code=201)
async def add_data(table_name: str, request: Request):
    # ... (Hàm này không thay đổi)
    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="No data provided")

    conn = None
    pk_column = None
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data',
            autocommit=False
        )
        cursor = conn.cursor()

        if table_name in ['thu_thu', 'ban_doc']:
            sdt_table = 'sdt_thu_thu' if table_name == 'thu_thu' else 'sdt_ban_doc'
            pk_column = 'ma_thu_thu' if table_name == 'thu_thu' else 'ma_ban_doc'
            
            if pk_column not in data or not data[pk_column]:
                 raise HTTPException(status_code=400, detail=f"Bắt buộc phải nhập '{pk_column}'.")

            new_id = data[pk_column]
            
            phone_numbers_str = data.pop('so_dien_thoai', None)
            
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            sql_insert_main = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(sql_insert_main, tuple(data.values()))
            
            if phone_numbers_str:
                new_phone_numbers = [num.strip() for num in phone_numbers_str.split(',') if num.strip()]
                if new_phone_numbers:
                    sql_insert_sdt = f"INSERT INTO {sdt_table} ({pk_column}, so_dien_thoai) VALUES (%s, %s)"
                    sdt_values = [(new_id, num) for num in new_phone_numbers]
                    cursor.executemany(sql_insert_sdt, sdt_values)
            
            conn.commit()
            return {"message": f"Data successfully added to {table_name}", "new_id": new_id}

        else:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            sql_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(sql_query, tuple(data.values()))
            conn.commit()
            return {"message": f"Data successfully added to {table_name}", "data": data}

    except Error as e:
        if conn: conn.rollback()
        if e.errno == 1062:
            key_value = data.get(pk_column, '') if pk_column else ''
            raise HTTPException(status_code=409, detail=f"Lỗi: Mã '{key_value}' đã tồn tại. Vui lòng chọn một mã khác.")
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# === HÀM XÓA DỮ LIỆU ĐÃ ĐƯỢC CẬP NHẬT ===
@api.delete("/delete/{table_name}/{primary_key_column}/{row_id}")
async def delete_data(table_name: str, primary_key_column: str, row_id: str):
    conn = None
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data',
            autocommit=False  # Tắt autocommit để quản lý transaction
        )
        cursor = conn.cursor()

        # Xử lý đặc biệt cho các bảng có dữ liệu phụ thuộc
        if table_name in ['thu_thu', 'ban_doc']:
            sdt_table = 'sdt_thu_thu' if table_name == 'thu_thu' else 'sdt_ban_doc'

            # Bước 1: Xóa các bản ghi phụ thuộc trong bảng số điện thoại trước
            sql_delete_sdt = f"DELETE FROM {sdt_table} WHERE {primary_key_column} = %s"
            cursor.execute(sql_delete_sdt, (row_id,))

            # Bước 2: Xóa bản ghi chính trong bảng cha
            sql_delete_main = f"DELETE FROM {table_name} WHERE {primary_key_column} = %s"
            cursor.execute(sql_delete_main, (row_id,))
        
        # Xử lý cho các bảng bình thường khác
        else:
            sql_query = f"DELETE FROM {table_name} WHERE {primary_key_column} = %s"
            cursor.execute(sql_query, (row_id,))
        
        # Kiểm tra xem có hàng nào ở bảng chính đã bị xóa không
        if cursor.rowcount == 0:
            conn.rollback()  # Hoàn tác lại giao dịch
            raise HTTPException(status_code=404, detail="Row not found or already deleted")
        
        # Nếu mọi thứ thành công, commit transaction
        conn.commit()

        return {"message": f"Row {row_id} from table {table_name} deleted successfully."}

    except Error as e:
        if conn:
            conn.rollback()  # Hoàn tác lại nếu có lỗi xảy ra
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@api.put("/update/{table_name}/{primary_key_column}/{row_id}")
async def update_data(table_name: str, primary_key_column: str, row_id: str, request: Request):
    # ... (Hàm này không thay đổi)
    data = await request.json()
    if not data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    conn = None
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='12345678',
            database='data',
            autocommit=False
        )
        cursor = conn.cursor()

        if table_name in ['thu_thu', 'ban_doc']:
            sdt_table = 'sdt_thu_thu' if table_name == 'thu_thu' else 'sdt_ban_doc'
            
            phone_numbers_str = data.pop('so_dien_thoai', None)
            
            if data:
                update_fields = ", ".join([f"{key} = %s" for key in data.keys()])
                sql_update_main = f"UPDATE {table_name} SET {update_fields} WHERE {primary_key_column} = %s"
                cursor.execute(sql_update_main, tuple(data.values()) + (row_id,))
            
            if phone_numbers_str is not None:
                sql_delete_sdt = f"DELETE FROM {sdt_table} WHERE {primary_key_column} = %s"
                cursor.execute(sql_delete_sdt, (row_id,))
                
                new_phone_numbers = [num.strip() for num in phone_numbers_str.split(',') if num.strip()]
                if new_phone_numbers:
                    sql_insert_sdt = f"INSERT INTO {sdt_table} ({primary_key_column}, so_dien_thoai) VALUES (%s, %s)"
                    sdt_values = [(row_id, num) for num in new_phone_numbers]
                    cursor.executemany(sql_insert_sdt, sdt_values)

            conn.commit()
            return {"message": f"Data in {table_name} updated successfully"}

        else:
            update_fields = ", ".join([f"{key} = %s" for key in data.keys()])
            sql_query = f"UPDATE {table_name} SET {update_fields} WHERE {primary_key_column} = %s"
            cursor.execute(sql_query, tuple(data.values()) + (row_id,))
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Row not found")

            conn.commit()
            return {"message": "Data updated successfully", "data": data}

    except Error as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"MySQL Error: {e}")
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def main():
    uvicorn.run("data:api", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()