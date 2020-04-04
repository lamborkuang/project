from django.contrib import admin
from user.models import * 
# Register your models here.


class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_active')

admin.site.register(User, UserAdmin)