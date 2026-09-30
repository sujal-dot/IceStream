#!/usr/bin/env python3
import os
import sys
import subprocess

def load_env():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v

def main():
    load_env()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sql_path = os.path.join(project_root, "flink", "jobs", "kafka_to_iceberg.sql")

    user = os.getenv("MINIO_ROOT_USER") or os.getenv("MINIO_ACCESS_KEY") or "icestream_minio"
    pwd = os.getenv("MINIO_ROOT_PASSWORD") or os.getenv("MINIO_SECRET_KEY") or "change-me-minio-secret"

    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    rendered = sql.replace("${MINIO_ROOT_USER}", user).replace("${MINIO_ROOT_PASSWORD}", pwd)
    if not rendered.strip().endswith("EXIT;"):
        rendered += "\nEXIT;\n"

    cmd = ["docker", "exec", "-i", "icestream-flink-jobmanager", "/opt/flink/bin/sql-client.sh"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(input=rendered, timeout=30)
    print("STDOUT:", out)
    print("STDERR:", err)

if __name__ == "__main__":
    main()
