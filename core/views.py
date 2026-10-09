from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView
from django.conf import settings
from core.models import NewsCategory, NewsPost
from national_client.utils import get_template_name
from core.apps import CoreConfig
from django.core.paginator import Paginator 
from .models import NewsPost, Testimonial

APP_NAME = CoreConfig.name


class Index(TemplateView):
    template_name = get_template_name("index.html", APP_NAME)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["testimonials"] = Testimonial.objects.filter(is_active=True)
        context["latest_news"] = (
            NewsPost.objects.published()
            .select_related("category")[:3]
        )
        return context
    

class Viamo_Getting_Started(TemplateView):
    template_name = get_template_name("viamo_getting_started.html", APP_NAME)

class About_Page(TemplateView):
    template_name = get_template_name("about.html", APP_NAME)



# ---- new views ----
def news_list(request):
    posts = NewsPost.objects.published().select_related("category")
    active_category = request.GET.get("category", "")
    if active_category:
        posts = posts.filter(category__slug=active_category)
 
    page_obj = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(request, "core/news_list.html", {
        "page_obj": page_obj,
        "categories": NewsCategory.objects.all(),
        "active_category": active_category,
    })
 
 
def news_detail(request, slug):
    post = get_object_or_404(
        NewsPost.objects.published().select_related("category"), slug=slug
    )
    others = NewsPost.objects.published().exclude(pk=post.pk).select_related("category")
    related = others.filter(category=post.category)[:3] if post.category else others[:0]
 
    return render(request, "core/news_detail.html", {
        "post": post,
        "recent_posts": others[:4],
        "related_posts": related,
        "categories": NewsCategory.objects.all(),
    })