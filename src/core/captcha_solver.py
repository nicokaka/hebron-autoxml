import time
import requests

class CaptchaSolverError(Exception):
    """Exceção levantada quando há erro no provedor de captcha."""
    pass

class CaptchaSolver:
    """
    Cliente genérico para resolução de hCaptcha usando APIs de terceiros.
    Suporta 2Captcha e CapSolver usando `requests` puro.
    """

    def __init__(self, api_key: str, provider: str = "2captcha"):
        self.api_key = api_key.strip()
        self.provider = provider.lower().strip()
        
        if not self.api_key:
            raise ValueError("API Key do provedor de captcha não configurada.")
            
        if self.provider not in ("2captcha", "capsolver"):
            raise ValueError(f"Provedor {self.provider} não é suportado.")

    def resolver_hcaptcha(self, sitekey: str, page_url: str, timeout: int = 180) -> str:
        """
        Envia a requisição para resolver o hCaptcha e aguarda (polling) pela resposta.
        Retorna o token gerado (g-recaptcha-response).
        Raises CaptchaSolverError se houver timeout ou erro na API.
        """
        if self.provider == "2captcha":
            return self._resolver_2captcha(sitekey, page_url, timeout)
        else:
            return self._resolver_capsolver(sitekey, page_url, timeout)

    def _resolver_2captcha(self, sitekey: str, page_url: str, timeout: int) -> str:
        # Enviar tarefa
        create_url = "https://2captcha.com/in.php"
        create_params = {
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1
        }
        
        try:
            resp = requests.post(create_url, data=create_params, timeout=10)
            data = resp.json()
        except Exception as e:
            raise CaptchaSolverError(f"Erro ao conectar com 2Captcha (criação): {e}")

        if data.get("status") != 1:
            raise CaptchaSolverError(f"Erro do 2Captcha (criação): {data.get('request', 'Desconhecido')}")

        task_id = data.get("request")
        
        # Aguardar resultado (polling)
        return self._poll_2captcha_result(task_id, timeout)

    def _poll_2captcha_result(self, task_id: str, timeout: int) -> str:
        res_url = "https://2captcha.com/res.php"
        res_params = {
            "key": self.api_key,
            "action": "get",
            "id": task_id,
            "json": 1
        }
        
        start_time = time.time()
        time.sleep(5)  # Espera inicial

        while time.time() - start_time < timeout:
            try:
                resp = requests.get(res_url, params=res_params, timeout=10)
                data = resp.json()
            except Exception as e:
                raise CaptchaSolverError(f"Erro ao conectar com 2Captcha (resultado): {e}")
                
            if data.get("status") == 1:
                return data.get("request")
                
            if data.get("request") != "CAPCHA_NOT_READY":
                raise CaptchaSolverError(f"Erro do 2Captcha (resultado): {data.get('request', 'Desconhecido')}")
                
            time.sleep(5)
            
        raise CaptchaSolverError(f"Timeout ao resolver Captcha via 2Captcha (>{timeout}s)")

    def _resolver_capsolver(self, sitekey: str, page_url: str, timeout: int) -> str:
        # Enviar tarefa
        create_url = "https://api.capsolver.com/createTask"
        payload = {
            "clientKey": self.api_key,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey
            }
        }
        
        try:
            resp = requests.post(create_url, json=payload, timeout=10)
            data = resp.json()
        except Exception as e:
            raise CaptchaSolverError(f"Erro ao conectar com CapSolver (criação): {e}")
            
        if data.get("errorId") != 0:
            err_msg = data.get("errorDescription") or data.get("errorCode", "Unknown")
            raise CaptchaSolverError(f"Erro do CapSolver (criação): {err_msg}")
            
        task_id = data.get("taskId")
        
        # Aguardar resultado
        return self._poll_capsolver_result(task_id, timeout)

    def _poll_capsolver_result(self, task_id: str, timeout: int) -> str:
        res_url = "https://api.capsolver.com/getTaskResult"
        payload = {
            "clientKey": self.api_key,
            "taskId": task_id
        }
        
        start_time = time.time()
        time.sleep(5)

        while time.time() - start_time < timeout:
            try:
                resp = requests.post(res_url, json=payload, timeout=10)
                data = resp.json()
            except Exception as e:
                raise CaptchaSolverError(f"Erro ao conectar com CapSolver (resultado): {e}")
                
            if data.get("errorId") != 0:
                err_msg = data.get("errorDescription") or data.get("errorCode", "Unknown")
                raise CaptchaSolverError(f"Erro do CapSolver (resultado): {err_msg}")
                
            status = data.get("status")
            if status == "ready":
                return data.get("solution", {}).get("gRecaptchaResponse")
            
            if status not in ("processing", "idle"):
                raise CaptchaSolverError(f"Status desconhecido do CapSolver: {status}")
                
            time.sleep(5)
            
        raise CaptchaSolverError(f"Timeout ao resolver Captcha via CapSolver (>{timeout}s)")
