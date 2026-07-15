#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drive_upload.py — envia um arquivo para uma pasta do Google Drive via service
account (escopo de ESCRITA). Se já existir arquivo com o mesmo nome na pasta,
ATUALIZA o conteúdo (não duplica) — re-execuções no mesmo mês substituem o arquivo.

Env: GOOGLE_SA_KEY (JSON) ou GOOGLE_SA_KEY_FILE ; GDRIVE_FOLDER_ID
Uso: python3 drive_upload.py <arquivo> [folder_id]
"""
import os, sys, json, mimetypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

def _creds():
    raw = os.environ.get("GOOGLE_SA_KEY")
    if raw:
        return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    p = os.environ.get("GOOGLE_SA_KEY_FILE")
    if p and os.path.exists(p):
        return service_account.Credentials.from_service_account_file(p, scopes=SCOPES)
    sys.exit("ERRO: defina GOOGLE_SA_KEY (JSON) ou GOOGLE_SA_KEY_FILE.")

def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python3 drive_upload.py <arquivo> [folder_id]")
    path = sys.argv[1]
    folder = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GDRIVE_FOLDER_ID")
    if not folder:
        sys.exit("ERRO: informe a pasta (arg2 ou GDRIVE_FOLDER_ID).")
    if not os.path.exists(path):
        sys.exit(f"ERRO: arquivo não encontrado: {path}")
    name = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    svc = build("drive", "v3", credentials=_creds(), cache_discovery=False)
    media = MediaFileUpload(path, mimetype=mime, resumable=False)
    safe = name.replace("'", "\\'")
    q = f"name = '{safe}' and '{folder}' in parents and trashed = false"
    res = svc.files().list(q=q, spaces="drive", fields="files(id,name)",
                           supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = res.get("files", [])
    if files:
        fid = files[0]["id"]
        svc.files().update(fileId=fid, media_body=media, supportsAllDrives=True).execute()
        print(f"[ok] Drive: atualizado '{name}' (id {fid})")
    else:
        meta = {"name": name, "parents": [folder]}
        f = svc.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True).execute()
        print(f"[ok] Drive: enviado '{name}' (id {f.get('id')})")

if __name__ == "__main__":
    main()
