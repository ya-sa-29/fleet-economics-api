from unittest.mock import patch, Mock
import requests
from src.services.minfin_parser import MinfinParser


@patch("src.services.minfin_parser.requests.get")
def test_fetch_current_prices_success(mock_get):
    html = """
    <table>
        <tr>
            <td>А-95</td>
            <td>Бензин</td>
            <td>56,79</td>
        </tr>
        <tr>
            <td>Дизельне пальне</td>
            <td>ДП</td>
            <td>54.99</td>
        </tr>
        <tr>
            <td>Газ автомобільний</td>
            <td>Газ</td>
            <td>34,50</td>
        </tr>
    </table>
    """

    mock_response = Mock()
    mock_response.text = html
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = MinfinParser.fetch_current_prices()

    assert result == {
        "a-95": 5679,
        "diesel": 5499,
        "gas": 3450,
    }

    mock_get.assert_called_once()

    #HTML не містить цін

@patch("src.services.minfin_parser.requests.get")

def test_fetch_current_prices_empty_html(mock_get):
    mock_response = Mock()
    mock_response.text = "<html><body><table></table></body></html>"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = MinfinParser.fetch_current_prices()

    assert result == {}

#Рядки мають менше трьох колонок
@patch("src.services.minfin_parser.requests.get")
def test_fetch_current_prices_skips_invalid_rows(mock_get):
    html = """
    <table>
        <tr>
            <td>А-95</td>
            <td>56,79</td>
        </tr>
        <tr>
            <td>Дизель</td>
            <td>Пальне</td>
        </tr>
    </table>
    """

    mock_response = Mock()
    mock_response.text = html
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = MinfinParser.fetch_current_prices()

    assert result == {}

@patch("src.services.minfin_parser.requests.get")
def test_fetch_current_prices_request_error(mock_get):
    mock_get.side_effect = requests.RequestException("Network error")

    result = MinfinParser.fetch_current_prices()

    assert result == {}

@patch("src.services.minfin_parser.requests.get")
def test_fetch_current_prices_excludes_premium_a95(mock_get):
    html = """
    <table>
        <tr>
            <td>А-95 Преміум</td>
            <td>Бензин</td>
            <td>60,99</td>
        </tr>
        <tr>
            <td>А-95</td>
            <td>Бензин</td>
            <td>56,79</td>
        </tr>
    </table>
    """

    mock_response = Mock()
    mock_response.text = html
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = MinfinParser.fetch_current_prices()

    assert result == {"a-95": 5679}