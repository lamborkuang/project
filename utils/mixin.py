from django.contrib.auth.decorators import login_required


class LoginRequiredMixin(object):
    
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredMixin, cls).as_view(**initkwargs)
        return login_required(view)

    
    def handle_no_permission(self):
        return redirect('http://127.0.0.1:8000/')