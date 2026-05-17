import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


class NVSConfig(BaseModel):
    ssid: Optional[str] = None
    password: Optional[str] = None
    home_district: Optional[int] = None
    device_name: Optional[str] = None
    legacy: Optional[int] = None
    fw_update_channel: Optional[int] = None
    led_pin: Optional[int] = None
    led_count: Optional[int] = None
    display_model: Optional[int] = None
    display_width: Optional[int] = None
    display_height: Optional[int] = None
    sound_source: Optional[int] = None
    buzzer_pin: Optional[int] = None


@app.post("/generate")
def generate_nvs(config: NVSConfig):
    rows = ["key,type,encoding,value"]

    if config.ssid:
        rows += [
            "wifi_nets,namespace,,",
            "count,data,u8,1",
            f"ssid0,data,string,{config.ssid}",
            f"pass0,data,string,{config.password or ''}",
        ]

    storage_rows = []
    if config.home_district is not None:
        storage_rows.append(f"hmd,data,i32,{config.home_district}")
    if config.device_name:
        storage_rows.append(f"dn,data,string,{config.device_name}")
    if config.legacy is not None:
        storage_rows.append(f"legacy,data,i32,{config.legacy}")
    if config.fw_update_channel is not None:
        storage_rows.append(f"fwuc,data,i32,{config.fw_update_channel}")
    if config.led_pin is not None:
        storage_rows.append(f"pp,data,i32,{config.led_pin}")
    if config.led_count is not None:
        storage_rows.append(f"pc,data,i32,{config.led_count}")
    if config.display_model is not None:
        storage_rows.append(f"dsmd,data,i32,{config.display_model}")
    if config.display_width is not None:
        storage_rows.append(f"dw,data,i32,{config.display_width}")
    if config.display_height is not None:
        storage_rows.append(f"dh,data,i32,{config.display_height}")
    if config.sound_source is not None:
        storage_rows.append(f"ss,data,i32,{config.sound_source}")
    if config.buzzer_pin is not None:
        storage_rows.append(f"bzp,data,i32,{config.buzzer_pin}")

    if not config.ssid and not storage_rows:
        raise HTTPException(status_code=400, detail="No configuration provided")

    if storage_rows:
        rows.append("storage,namespace,,")
        rows.extend(storage_rows)

    csv_content = "\n".join(rows) + "\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "config.csv"
        bin_path = Path(tmpdir) / "nvs.bin"
        csv_path.write_text(csv_content, encoding="utf-8")

        result = subprocess.run(
            ["python", "-m", "esp_idf_nvs_partition_gen", "generate",
             str(csv_path), str(bin_path), "0x5000"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr or result.stdout)

        nvs_binary = bin_path.read_bytes()

    return Response(content=nvs_binary, media_type="application/octet-stream")
