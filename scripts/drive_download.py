#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa as bases do Google Drive (Alunos Ativos + Acessos Catraca) usando uma
Service Account, gravando data/<fileId>.bin e data/manifest.json {id: title}.
Tambem grava data/meta.json com a data de atualizacao mais recente da base
e o e-mail de quem atualizou (lastModifyingUser), para exibir no dashboard.

Autenticacao:
  - GOOGLE_SA_KEY      : conteudo JSON da chave da service account, OU
  - GOOGLE_SA_KEY_FILE : caminho para o arquivo JSON da chave.
"""
import os, sys, io, json, datetime
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    TZ = None

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data"
FOLDER_ALUNOS  = os.environ.get("FOLDER_ALUNOS",  "1U5prMp9ImJ3mR1flWanictD4rb4u0GRc")
FOLDER_CATRACA = os.environ.get("FOLDER_CATRACA", "1-vdLb3wO_wfT_trX9Bl0p83SYxGzCA9_")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FIELDS = ("nextPageToken, files(id, name, mimeType, modifiedTime, "
          "lastModifyingUser(emailAddress, displayName))")

def load_credentials():
    raw = os.environ.get("GOOGLE_SA_KEY")
    if raw:
        return service_account.Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    path = os.environ.get("GOOGLE_SA_KEY_FILE")
    if path and os.path.exists(path):
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    sys.exit("ERRO: defina GOOGLE_SA_KEY (JSON) ou GOOGLE_SA_KEY_FILE (caminho).")

def list_children(svc, folder_id):
    files, token = [], None
    q = f"'{folder_id}' in parents and trashed = false"
    while True:
        resp = svc.files().list(
            q=q, spaces="drive", fields=FIELDS, pageToken=token, pageSize=100,
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
    latest = None  # (modifiedTime_str, email, name)
    for folder_id in (FOLDER_ALUNOS, FOLDER_CATRACA):
        for f in list_children(svc, folder_id):
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
            mt = f.get("modifiedTime", "")
            if mt and (latest is None or mt > latest[0]):
                lu = f.get("lastModifyingUser") or {}
                latest = (mt, lu.get("emailAddress", ""), lu.get("displayName", ""))
            print(f"[ok] {name}  ({os.path.getsize(dest)} bytes)")

    with open(os.path.join(DATA_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    # ---- meta.json: data de atualizacao da base + autor ----
    meta = {"baseUpdated": "", "baseUpdatedBy": "", "baseUpdatedByName": ""}
    if latest:
        mt, email, dispname = latest
        try:
            dt = datetime.datetime.fromisoformat(mt.replace("Z", "+00:00"))
            if TZ: dt = dt.astimezone(TZ)
            meta["baseUpdated"] = dt.strftime("%d.%m.%Y")
        except Exception:
            meta["baseUpdated"] = mt[:10]
        meta["baseUpdatedBy"] = email or ""
        meta["baseUpdatedByName"] = dispname or ""
    with open(os.path.join(DATA_DIR, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)

    print(f"[info] alunos={n_alunos} catraca={n_catraca} total={len(manifest)}")
    print(f"[info] baseUpdated={meta['baseUpdated']} by={meta['baseUpdatedBy'] or meta['baseUpdatedByName']}", file=sys.stderr)
    if n_alunos == 0 or n_catraca == 0:
        sys.exit("ERRO: faltam arquivos de Alunos Ativos ou Acessos Catraca (verifique o compartilhamento das pastas com a service account).")

if __name__ == "__main__":
    main()
