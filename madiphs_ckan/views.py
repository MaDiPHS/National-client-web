from concurrent.futures import ThreadPoolExecutor
import csv
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView
import requests

from madiphs_ckan.apps import MadiphsCkanConfig
from django.http import JsonResponse

# Create your views here.
APP_NAME = MadiphsCkanConfig.name

class Ckan(TemplateView):
    template_name ='madiphs_ckan/ckan.html'



class CkanGettingStarted(TemplateView):

    template_name ='madiphs_ckan/ckan_getting_started.html'
    def fetch_organization_details(self, org_id):
        """Fetch detailed info for one organization."""
        org_detail_url = f"https://ckan.madiphs.org/api/3/action/organization_show?id={org_id}"
        try:
            response = requests.get(org_detail_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    result = data['result']
                    return {
                        'name': result['name'],
                        'title': result.get('title', ''),
                        'description': result.get('description', ''),
                        'package_count': result.get('package_count', 0)
                    }
        except Exception as e:
            return {'name': org_id, 'title': '', 'description': f'Error: {str(e)}', 'package_count': 0}
        return None

    def get_organization_data(self):
        """Fetch list of organizations and their metadata concurrently."""
        org_list_url = "https://ckan.madiphs.org/api/3/action/organization_list"
        try:
            response = requests.get(org_list_url, timeout=10)
            if response.status_code == 200:
                orgs_data = response.json()
                if orgs_data.get('success'):
                    org_ids = orgs_data['result']
                    
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        results = list(executor.map(self.fetch_organization_details, org_ids))

                    # Filter out any `None` responses (failed fetches)
                    return [org for org in results if org]
        except Exception as e:
            return [{"name": "Error", "title": "", "description": f"Could not fetch organizations: {str(e)}", "package_count": 0}]

        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organizations'] = self.get_organization_data()
        return context

class CkanGettingStarted2(TemplateView):
    template_name = 'madiphs_ckan/ckan_getting_started2.html'

    def fetch_tags(self):
        """Fetch all tags from CKAN."""
        url = "https://ckan.madiphs.org/api/3/action/tag_list"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return [{"name": tag} for tag in data["result"]]
        except Exception as e:
            return [{"name": f"Error fetching tags: {str(e)}"}]
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = self.fetch_tags()
        return context


class CkanGettingStarted3(TemplateView):
    template_name = 'madiphs_ckan/ckan_getting_started3.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def post(self, request, *args, **kwargs):
        query = request.POST.get("query", "").strip()
        download = request.POST.get("download", "")  # If "Download CSV" button is clicked

        errors = {}
        if not query:
            errors['query'] = "Please enter a keyword or author to search."

        if errors:
            return render(request, self.template_name, {"errors": errors, "form_data": request.POST})

        api_url = f"https://ckan.madiphs.org/api/3/action/package_search?q={query}"
        response = requests.get(api_url)

        if response.status_code != 200:
            return HttpResponse("Failed to fetch data from CKAN API. Please try again later.", status=500)

        results = response.json().get("result", {}).get("results", [])

        # Prepare dataset rows
        datasets = []
        for item in results:
            author = item.get("author", "Unknown")
            org = item.get("organization", {}).get("title", "Unknown")
            title = item.get("title", item.get("name", "No Title"))
            url = f"https://ckan.madiphs.org/dataset/{item.get('name', '')}"
            description = item.get("notes", "No description provided.")
            datasets.append([author, org, title, url, description])

        # Handle CSV download
        if download:
            response_csv = HttpResponse(content_type='text/csv')
            response_csv['Content-Disposition'] = 'attachment; filename="ckan_datasets_results.csv"'
            writer = csv.writer(response_csv)
            writer.writerow(["Author", "Organization", "Title / Name of Dataset", "URL to Dataset", "Description"])
            for data in datasets:
                writer.writerow(data)
            return response_csv

        return render(request, self.template_name, {
            "datasets": datasets,
            "form_data": {"query": query},
            "search_term": query
        })

import json

# Map form values → EPPO URIs used in CKAN
CROP_URI_MAP = {
    "maize":     "https://gd.eppo.int/taxon/ZEAMX",
    "tomato":    "https://gd.eppo.int/taxon/LYPES",
    "groundnut": "https://gd.eppo.int/taxon/ARHHY",
    "soybean":   "https://gd.eppo.int/taxon/GLXMA",
    "cassava":   "https://gd.eppo.int/taxon/MANES",
    "banana":    "https://gd.eppo.int/taxon/MUBPA",
}

def AdvancedFilter(request):
    crop = request.GET.get("crop")
    pest = request.GET.getlist("pest")
    country = request.GET.get("country")
    dtype = request.GET.get("type")
    show_all = request.GET.get("show_all") == "true"

    filtered = []
    has_active_filters = bool(crop or pest or country or dtype)

    # Convert crop name → URI for matching against CKAN data
    crop_uri = CROP_URI_MAP.get(crop) if crop else None

    if show_all or has_active_filters:
        response = requests.get(
            "https://ckan.madiphs.org/api/3/action/package_search?rows=100000"
        )
        datasets = response.json().get("result", {}).get("results", [])

        def matches(dataset):
            dataset_crops     = dataset.get("crop", [])          # already a list of URIs
            dataset_pests     = dataset.get("pest", [])          # already a list of URIs
            dataset_countries = dataset.get("country_codes", []) # already a list of codes
            dataset_type      = dataset.get("type", "")

            if crop_uri and crop_uri not in dataset_crops:
                return False
            if pest and not any(p in dataset_pests for p in pest):
                return False
            if country and country not in dataset_countries:
                return False
            if dtype and dtype != dataset_type:
                return False
            return True

        filtered = datasets if show_all else [d for d in datasets if matches(d)]

    context = {
        "datasets": [
            (
                d.get("author", "Unknown"),
                d.get("organization", {}).get("title", "N/A"),
                d.get("title", "Untitled"),
                f"https://ckan.madiphs.org/dataset/{d.get('name')}" if d.get("name") else "",
                d.get("notes", "")[:250]
            ) for d in filtered
        ],
        "search_params": request.GET,
        "selected_pests": pest,
        "has_active_filters": has_active_filters,
    }

    return render(request, "madiphs_ckan/advanced_filter.html", context)
