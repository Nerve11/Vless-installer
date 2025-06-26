import os
import sys
import json
import subprocess
import uuid

def run_command(command, capture_output=False, text=False, check=True):
    """Executes a shell command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=30
        )
        if capture_output:
            return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        if check:
            print(f"Ошибка при выполнении команды: {command}\n{e}")
            sys.exit(1)
        return None
    return None

def check_root():
    """Checks if the script is run as root."""
    if os.geteuid() != 0:
        print("Этот скрипт необходимо запускать с правами суперпользователя (root).")
        sys.exit(1)

def get_server_ip():
    """Gets the public IP address of the server from multiple sources."""
    ip_services = ["https://api.ipify.org", "https://ipinfo.io/ip", "https://icanhazip.com"]
    for service in ip_services:
        print(f"Пытаюсь получить IP-адрес с помощью {service}...")
        ip = run_command(f"curl -s {service}", capture_output=True, text=True, check=False)
        if ip and ('.' in ip or ':' in ip): # Basic validation for an IP address
            print(f"IP-адрес успешно получен: {ip}")
            return ip
    return None

def install_xray():
    """Installs Xray-core using the official script."""
    print("Установка Xray-core...")
    # Ensure curl is installed
    run_command("apt-get update && apt-get install -y curl", check=False)
    install_script_url = "https://github.com/XTLS/Xray-install/raw/main/install-release.sh"
    run_command(f"bash -c \"$(curl -L {install_script_url})\" @ install")
    print("Xray-core успешно установлен.")

def generate_xray_credentials():
    """Generates UUID and private/public keys for Xray."""
    print("Генерация ключей и UUID...")
    client_uuid = str(uuid.uuid4())
    # Ensure openssl is installed for random hex generation
    run_command("apt-get install -y openssl", check=False)
    keys = run_command("/usr/local/bin/xray x25519", capture_output=True, text=True)
    private_key = keys.split('\n')[0].split(': ')[1]
    public_key = keys.split('\n')[1].split(': ')[1]
    short_id = run_command("openssl rand -hex 8", capture_output=True, text=True)
    return client_uuid, private_key, public_key, short_id

def create_xray_config(client_uuid, private_key, short_id, server_name):
    """Creates the Xray config.json file."""
    print("Создание конфигурационного файла...")
    config = {
        "log": {
            "loglevel": "warning"
        },
        "inbounds": [
            {
                "listen": "0.0.0.0",
                "port": 443,
                "protocol": "vless",
                "settings": {
                    "clients": [
                        {
                            "id": client_uuid,
                            "flow": "xtls-rprx-vision"
                        }
                    ],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{server_name}:443",
                        "xver": 0,
                        "serverNames": [server_name],
                        "privateKey": private_key,
                        "shortIds": [short_id]
                    }
                }
            }
        ],
        "outbounds": [
            {
                "protocol": "freedom",
                "tag": "direct"
            },
            {
                "protocol": "blackhole",
                "tag": "block"
            }
        ]
    }
    # Ensure the directory exists
    os.makedirs("/usr/local/etc/xray", exist_ok=True)
    with open("/usr/local/etc/xray/config.json", "w") as f:
        json.dump(config, f, indent=4)
    print("Конфигурационный файл успешно создан: /usr/local/etc/xray/config.json")

def restart_xray():
    """Restarts and enables the Xray service."""
    print("Перезапуск и активация сервиса Xray...")
    run_command("systemctl restart xray")
    run_command("systemctl enable xray")
    print("Сервис Xray запущен и добавлен в автозагрузку.")

def generate_share_link(server_ip, client_uuid, public_key, short_id, server_name):
    """Generates and displays the client share link."""
    print("\n" + "="*40)
    print("--- Конфигурация клиента ---")
    print("="*40)
    share_link = (
        f"vless://{client_uuid}@{server_ip}:443?"
        f"security=reality&encryption=none&pbk={public_key}&"
        f"headerType=none&fp=chrome&sid={short_id}&"
        f"sni={server_name}&flow=xtls-rprx-vision&"
        f"type=tcp#REALITY-{server_ip}"
    )
    print("\nСсылка для импорта в клиент (например, v2rayNG, NekoBox, Streisand):")
    print(share_link)
    print("\n" + "="*40)


def main():
    """Main function to run the installation process."""
    check_root()
    
    # Check OS
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            if 'ubuntu' not in f.read().lower():
                print("Внимание: Этот скрипт предназначен для Ubuntu, но может работать и на других Debian-подобных системах.")
    else:
        print("Не удалось определить ОС. Убедитесь, что вы используете Debian-подобную систему.")


    server_ip = get_server_ip()
    if not server_ip:
        print("Не удалось определить публичный IP-адрес сервера. Прерывание.")
        sys.exit(1)

    # Prompt for the server name to impersonate
    default_server_name = "www.microsoft.com"
    server_name_input = input(
        f"\nВведите доменное имя для маскировки (SNI) [нажмите Enter, чтобы использовать {default_server_name}]: "
    )
    server_name = server_name_input.strip() or default_server_name
    print(f"Используется SNI: {server_name}")

    install_xray()
    client_uuid, private_key, public_key, short_id = generate_xray_credentials()
    create_xray_config(client_uuid, private_key, short_id, server_name)
    restart_xray()
    generate_share_link(server_ip, client_uuid, public_key, short_id, server_name)
    
    print("\nУстановка успешно завершена!")
    print("Используйте сгенерированную ссылку для настройки вашего VPN-клиента.")

if __name__ == "__main__":
    main()