import os
import requests
import json
from datetime import datetime
from threading import Thread

class EvolutionService:
    @staticmethod
    def get_api_url():
        url = os.environ.get('EVOLUTION_API_URL', '').rstrip('/')
        if not url:
            raise ValueError("EVOLUTION_API_URL não configurada no ambiente (Vercel).")
        
        if not url.startswith('http'):
            url = f"https://{url}"
            
        return url
        
    @staticmethod
    def get_api_key():
        key = os.environ.get('EVOLUTION_API_KEY', '')
        if not key:
            raise ValueError("EVOLUTION_API_KEY não configurada no ambiente (Vercel).")
        return key
        
    @staticmethod
    def get_headers():
        return {
            'Content-Type': 'application/json',
            'apikey': EvolutionService.get_api_key()
        }

    @staticmethod
    def create_instance(instance_name):
        """Creates a new instance in Evolution API v1/v2"""
        url = f"{EvolutionService.get_api_url()}/instance/create"
        payload = {
            "instanceName": instance_name,
            "token": "", 
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS" # Required for v2.x
        }
        try:
            response = requests.post(
                url, 
                json=payload, 
                headers=EvolutionService.get_headers(),
                timeout=15,
                verify=False
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_connection_status(instance_name):
        url = f"{EvolutionService.get_api_url()}/instance/connectionState/{instance_name}"
        try:
            response = requests.get(
                url, 
                headers=EvolutionService.get_headers(), 
                timeout=5,
                verify=False
            )
            return response.json()
        except:
            return {"instance": {"state": "disconnected"}}

    @staticmethod
    def get_qrcode(instance_name):
        """Fetches the QR code for an existing instance using GET /instance/connect"""
        url = f"{EvolutionService.get_api_url()}/instance/connect/{instance_name}"
        try:
            response = requests.get(
                url, 
                headers=EvolutionService.get_headers(), 
                timeout=15,
                verify=False
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def connect_instance(instance_name):
        """Initiates connection and gets QR via POST /instance/connect (Evolution v2 style)"""
        url = f"{EvolutionService.get_api_url()}/instance/connect/{instance_name}"
        try:
            response = requests.post(
                url, 
                headers=EvolutionService.get_headers(), 
                timeout=15,
                verify=False
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def logout_instance(instance_name):
        """Logs out from an instance"""
        url = f"{EvolutionService.get_api_url()}/instance/logout/{instance_name}"
        try:
            response = requests.delete(url, headers=EvolutionService.get_headers(), verify=False)
            return response.json()
        except:
            return {"status": 404}
        
    @staticmethod
    def delete_instance(instance_name):
        """Deletes an instance from the server"""
        url = f"{EvolutionService.get_api_url()}/instance/delete/{instance_name}"
        try:
            response = requests.delete(url, headers=EvolutionService.get_headers(), verify=False)
            return response.json()
        except:
            return {"status": 404}

    @staticmethod
    def configure_webhook(instance_name, webhook_url):
        url = f"{EvolutionService.get_api_url()}/webhook/set/{instance_name}"
        payload = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "webhookByEvents": False,
                "events": [
                    "APPLICATION_STARTUP",
                    "QRCODE_UPDATED",
                    "MESSAGES_SET",
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE",
                    "MESSAGES_DELETE",
                    "SEND_MESSAGE",
                    "CONNECTION_UPDATE",
                    "CALL"
                ]
            }
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()

    @staticmethod
    def send_text(instance_name, number, text):
        url = f"{EvolutionService.get_api_url()}/message/sendText/{instance_name}"
        if not number.endswith("@s.whatsapp.net") and not number.endswith("@g.us"):
            number = f"{number}@s.whatsapp.net"
            
        payload = {
            "number": number,
            "text": text,
            "delay": 1200
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()

    @staticmethod
    def send_media(instance_name, number, media_url, media_type="image", caption=""):
        url = f"{EvolutionService.get_api_url()}/message/sendMedia/{instance_name}"
        if not number.endswith("@s.whatsapp.net") and not number.endswith("@g.us"):
            number = f"{number}@s.whatsapp.net"
            
        payload = {
            "number": number,
            "mediatype": media_type,
            "media": media_url,
            "caption": caption
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()
        
    @staticmethod
    def send_audio(instance_name, number, audio_url):
        url = f"{EvolutionService.get_api_url()}/message/sendWhatsAppAudio/{instance_name}"
        if not number.endswith("@s.whatsapp.net") and not number.endswith("@g.us"):
            number = f"{number}@s.whatsapp.net"
            
        payload = {
            "number": number,
            "audio": audio_url
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()

    @staticmethod
    def send_reaction(instance_name, number, message_id, reaction="👍"):
        url = f"{EvolutionService.get_api_url()}/message/sendReaction/{instance_name}"
        payload = {
            "remoteJid": number,
            "messageId": message_id,
            "reaction": reaction
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()

    @staticmethod
    def send_location(instance_name, number, name, address, latitude, longitude):
        url = f"{EvolutionService.get_api_url()}/message/sendLocation/{instance_name}"
        payload = {
            "number": number,
            "name": name,
            "address": address,
            "latitude": latitude,
            "longitude": longitude
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()
        
    @staticmethod
    def send_contact_card(instance_name, number, contact_name, contact_phone):
        url = f"{EvolutionService.get_api_url()}/message/sendContact/{instance_name}"
        payload = {
            "number": number,
            "contact": {
                "fullName": contact_name,
                "wuid": contact_phone
            }
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()

    @staticmethod
    def get_all_groups(instance_name):
        url = f"{EvolutionService.get_api_url()}/group/fetchAllGroups/{instance_name}?getParticipants=false"
        response = requests.get(url, headers=EvolutionService.get_headers())
        return response.json()

    @staticmethod
    def create_group(instance_name, subject, participants):
        url = f"{EvolutionService.get_api_url()}/group/createGroup/{instance_name}"
        payload = {
            "subject": subject,
            "participants": participants
        }
        response = requests.post(url, headers=EvolutionService.get_headers(), json=payload)
        return response.json()
        
    @staticmethod
    def get_group_members(instance_name, group_jid):
        url = f"{EvolutionService.get_api_url()}/group/participants/{instance_name}?groupJid={group_jid}"
        response = requests.get(url, headers=EvolutionService.get_headers())
        return response.json()
