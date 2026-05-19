from django.core.paginator import InvalidPage
from django.db.models import F
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from helper_files.status_code import StatusCode


class PaginationHelper(PageNumberPagination):
    page_size = 10
    page_query_param = 'page_number'
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            'status': StatusCode.success,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_number_of_objects': self.page.paginator.count,
            'number_of_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'last_page': self.page.paginator.num_pages,
            'count_items_in_page': len(self.page.object_list),
            'results': data,
        })

    @staticmethod
    def set_default_page_number_and_page_size(request):
        request.GET._mutable = True
        if 'page_size' not in request.GET:
            request.GET['page_size'] = 10
        if 'page_number' not in request.GET:
            request.GET['page_number'] = '1'

    def paginate_queryset(self, queryset, request, view=None):
        if not queryset.ordered:
            queryset = queryset.order_by(F('id').desc())
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)
        try:
            self.page = paginator.page(page_number)
        except InvalidPage:
            raise NotFound({'message': 'Invalid page.', 'status': StatusCode.not_found})
        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True
        self.request = request
        return list(self.page)
