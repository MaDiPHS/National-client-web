# admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import NewsCategory, NewsPost, Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(ModelAdmin):
    list_display = [
        'display_name',
        'display_role',
        'display_rating',
        'display_is_active',
        'display_order',
    ]
    list_editable = ( 'display_order',)
    search_fields = ('name', 'role', 'quote')
    list_per_page = 50

    @display(description='Name', ordering='name')
    def display_name(self, obj):
        return obj.name

    @display(description='Role', ordering='role')
    def display_role(self, obj):
        return obj.role

    @display(description='Rating', ordering='rating')
    def display_rating(self, obj):
        return obj.rating

    @display(description='Active', ordering='is_active', boolean=True)
    def display_is_active(self, obj):
        return obj.is_active

    @display(description='Order', ordering='display_order')
    def display_order(self, obj):
        return obj.display_order


@admin.register(NewsCategory)
class NewsCategoryAdmin(ModelAdmin):
    list_display = [
        'display_name',
        'display_slug',
    ]
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 50

    @display(description='Name', ordering='name')
    def display_name(self, obj):
        return obj.name

    @display(description='Slug', ordering='slug')
    def display_slug(self, obj):
        return obj.slug


@admin.register(NewsPost)
class NewsPostAdmin(ModelAdmin):
    list_display = [
        'display_title',
        'display_category',
        'display_author_name',
        'display_published_at',
        'display_is_published',
    ]
    list_filter = ('is_published', 'category')
 
    search_fields = ('title', 'excerpt', 'content')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    list_per_page = 50

    @display(description='Title', ordering='title')
    def display_title(self, obj):
        return obj.title

    @display(description='Category', ordering='category')
    def display_category(self, obj):
        return obj.category

    @display(description='Author', ordering='author_name')
    def display_author_name(self, obj):
        return obj.author_name

    @display(description='Published At', ordering='published_at')
    def display_published_at(self, obj):
        if obj.published_at:
            return obj.published_at.strftime('%Y-%m-%d %H:%M')
        return '—'

    @display(description='Published', ordering='is_published', boolean=True)
    def display_is_published(self, obj):
        return obj.is_published