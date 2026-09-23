from django.shortcuts import render


def gridmap_example(request):
    # return render(request, 'charts/charts.html', {})
    return render(request, 'gridmap/example.html', {})


def gridmap_example2(request):
    # return render(request, 'charts/charts.html', {})
    return render(request, 'gridmap/example.html', {})


def gridmap_example4(request):
    # return render(request, 'charts/charts.html', {})
    return render(request, 'gridmap/example.html', {})

def gridmap_example5(request):
    # return render(request, 'charts/charts.html', {})
    return render(request, 'gridmap/example.html', {})

# Serving settings for JavaScript
def settings_js(request):
    user_agent = request.META['HTTP_USER_AGENT']
    user_is_ie = False
    if user_agent.find("MSIE") >= 0 or user_agent.find("Trident") >= 0:
        user_is_ie = True
    context = {
        # 'crop_categories': CropCategory.get_crop_categories_from_vipslogic_as_text(),
        'user_is_ie': user_is_ie,
    }
    return render(request, 'gridmap/settings.js', context, content_type="application/javascript;charset=UTF-8")
