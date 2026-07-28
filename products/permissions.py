from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """
    Requirement (2.1.2): "Admin can create, update, delete products" while
    "Users can view product lists and details." Read access is public;
    write access requires staff/admin.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
