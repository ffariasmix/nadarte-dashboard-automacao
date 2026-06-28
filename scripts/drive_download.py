#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa as bases do Google Drive (Alunos Ativos + Acessos Catraca) usando uma
Service Account, gravando data/<fileId>.bin e data/manifest.json {id: title}
no formato esperado por build_freq_multi.py.

Autenticacao:
  - GOOGLE_SA_KEY      : conteudo JSON da chave da service account (recomendado, via secret), OU
  - GOOGLE_SA_KEY_FILE : caminho para o arquivo JSON da chave.

IDs das pastas (sobrescreviveis por env):
  - FOLDER_ALUNOS  (default = Alunos Ativos)
  - FOLDER_CATRACA (default = Acessos Catraca)

Uso: python scripts/drive_download.py [data_dir]
"""
import os, sys, io, json, base64

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"
FOLDER_ALUNOS  = os.environ.get("FOLDER_ALUNOS",  "1U5prMp9ImJ3mR1flWanictD4rb4u0GRc")
FOLDER_CATRACA = os.environ.get("FOLDER_CATRACA", "1-vdLb3wO_wfT_trX9Bl0p83SYxGzCA9_")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def load_credentials():
    raw = os.environ.get("GOOGLE_SA_KEY")
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    path = os.environ.get("GOOGLE_SA_KEY_FILE")
    if path and os.path.exists(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    sys.exit("ERRO: defina GOOGLE_SA_KEY (JSON) ou GOOGLE_SA_KEY_FILE (caminho).")

def list_children(svc, folder_id):
    files, token = [], None
    q = f"'{folder_id}' in parents and trashed = false"
    while True:
        resp = svc.files().list(
            q=q, spaces="drive",
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=token, pageSize=100,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return files

def download(svc, file_id, dest):
    req = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.FileIO(dest, "wb")
    dl = MediaIoBaseDownload(buf, req, chunksize=1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk()
    buf.close()

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    creds = load_credentials()
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    manifest = {}
    n_alunos = n_catraca = 0
    for folder_id, kind in [(FOLDER_ALUNOS, "Alunos Ativos"), (FOLDER_CATRACA, "Acessos Catr")]:
        children = list_children(svc, folder_id)
        for f in children:
            name = f.get("name", "")
            if f.get("mimeType") != XLSX_MIME:
                continue
            if ("Alunos Ativos" not in name) and ("Acessos Catr" not in name):
                continue
            dest = os.path.join(DATA_DIR, f["id"] + ".bin")
            download(svc, f["id"], dest)
            manifest[f["id"]] = name
            if "Alunos Ativos" in name: n_alunos += 1
            else: n_catraca += 1
            print(f"[ok] {name}  ({os.path.getsize(dest)} bytes)")

    with open(os.path.join(DATA_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    print(f"[info] alunos={n_alunos} catraca={n_catraca} total={len(manifest)}")
    if n_alunos == 0 or n_catraca == 0:
        sys.exit("ERRO: faltam arquivos de Alunos Ativos ou Acessos Catraca (verifique o compartilhamento das pastas com a service account).")

if __name__ == "__main__":
    main()
