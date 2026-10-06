import requests
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinfinParser:
    URL = "https://index.minfin.com.ua/ua/markets/fuel/"

    @classmethod
    def fetch_current_prices(cls) -> dict:
        """
        Йде на Мінфін, парсить реальні ціни і повертає словник у копійках.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(cls.URL, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            parsed_prices = {}

            rows = soup.find_all("tr")
            
            for row in rows:
                tds = row.find_all("td")
                
                # Тепер перевіряємо, чи є хоча б 3 колонки
                if len(tds) >= 3:
                    fuel_name = tds[0].get_text(strip=True).lower()
                    # Беремо ціну з ТРЕТЬОЇ колонки (індекс 2)
                    price_text = tds[2].get_text(strip=True)
                    
                    match = re.search(r'(\d{2}[.,]\d{2})', price_text)
                    
                    if match:
                        price_str = match.group(1).replace(',', '.')
                        price_kopecks = int(float(price_str) * 100)
                        
                        # Використовуємо 'in' замість '==' для захисту від прихованих символів
                        if "а-95" in fuel_name and "преміум" not in fuel_name:
                            parsed_prices["a-95"] = price_kopecks
                        elif "дизель" in fuel_name:
                            parsed_prices["diesel"] = price_kopecks
                        elif "газ" in fuel_name:
                            parsed_prices["gas"] = price_kopecks
            
            if not parsed_prices:
                logger.warning("Не вдалося знайти ціни. Можливо, Мінфін змінив верстку.")
                return {}
                
            logger.info(f"Успішно отримано реальні ціни: {parsed_prices}")
            return parsed_prices

        except Exception as e:
            logger.error(f"Помилка парсингу Мінфіну: {e}")
            return {}