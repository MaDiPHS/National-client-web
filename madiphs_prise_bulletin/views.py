from django.shortcuts import render
import requests
from django.http import JsonResponse



PRISE_API_BASE = "https://prise.org/wp-json/custom/v1"


def bulletin_proxy(request, path=""):
    """
    Proxy requests from the browser to the PRISE API.
    This avoids browser CORS restrictions.
    """
    url = f"{PRISE_API_BASE}/{path.lstrip('/')}"

    try:
        response = requests.get(
            url,
            params=request.GET,
            timeout=30,
        )

        response.raise_for_status()

        return JsonResponse(
            response.json(),
            safe=False,
            status=response.status_code,
        )

    except requests.RequestException as exc:
        return JsonResponse(
            {
                "error": "Failed to connect to PRISE API",
                "details": str(exc),
            },
            status=502,
        )

    except ValueError:
        return JsonResponse(
            {
                "error": "PRISE API returned invalid JSON"
            },
            status=502,
        )


def bulletin_example(request):
    return render(
        request,
        "madiphs_prise_bulletin/example.html",
        {}
    )

# Create your views here.
def bulletin_intro(request):
    return render(request,"madiphs_prise_bulletin/intro.html", {})

