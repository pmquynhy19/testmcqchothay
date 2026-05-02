# Quiz Online

Day la ban web app co server de hoc sinh lam bai tai nha bang dien thoai/laptop.

## Chay thu tren may

```powershell
cd quiz_online
python -m pip install -r requirements.txt
python app.py
```

Mo:

```text
http://127.0.0.1:5000
```

Trang giao vien:

```text
http://127.0.0.1:5000/admin
```

Mat khau mac dinh:

```text
123456
```

Khi dua len online, hay doi bien moi truong:

```text
ADMIN_PASSWORD=mat-khau-giao-vien-cua-ban
SECRET_KEY=chuoi-bi-mat-bat-ky
```

## Dua len online cho hoc sinh lam tai nha

Voi 100 hoc sinh, nen dung hosting co server that, vi free tier yeu co the cham neu nop bai cung luc.

### Phuong an de thao tac: Render

1. Tao tai khoan Render.
2. Tao repository GitHub chua thu muc `quiz_online`.
3. Tren Render, chon `New Web Service`.
4. Build command:

```text
pip install -r requirements.txt
```

5. Start command:

```text
gunicorn app:app
```

6. Them environment variables:

```text
ADMIN_PASSWORD=mat-khau-giao-vien-cua-ban
SECRET_KEY=chuoi-bi-mat-bat-ky
```

7. Deploy, sau do Render se cho link dang:

```text
https://ten-app.onrender.com
```

## Luu y ve du lieu

Ban hien tai dung SQLite file `submissions.db`.

Neu hosting xoa file khi restart/deploy, ket qua co the mat. De thi that nghiem tuc, nen:

- xuat Excel ngay sau khi thi, hoac
- dung VPS co o dia ben vung, hoac
- nang cap sang PostgreSQL/Supabase.

## Link can gui

Hoc sinh:

```text
https://ten-web-cua-ban/
```

Giao vien:

```text
https://ten-web-cua-ban/admin
```
