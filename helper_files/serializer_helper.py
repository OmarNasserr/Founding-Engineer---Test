from rest_framework.exceptions import ValidationError


class SerializerHelper:

    @staticmethod
    def is_valid(self, *, raise_exception=False):
        assert hasattr(self, 'initial_data'), (
            'Cannot call `.is_valid()` as no `data=` keyword argument was '
            'passed when instantiating the serializer instance.'
        )

        if not hasattr(self, '_validated_data'):
            try:
                self._validated_data = self.run_validation(self.initial_data)
            except ValidationError as exc:
                self._validated_data = {}
                self._errors = exc.detail
            else:
                self._errors = {}

        if self._errors and raise_exception:
            raise ValidationError(self.errors)

        err = SerializerHelper._extract_first_error(self._errors) if self._errors else 'no errors were returned'
        return not bool(self._errors), err

    @staticmethod
    def _extract_first_error(errors, field_path=None):
        if isinstance(errors, dict):
            for field, error in errors.items():
                current_path = f'{field_path}.{field}' if field_path else field
                result = SerializerHelper._extract_first_error(error, current_path)
                if result:
                    return result
        elif isinstance(errors, list):
            if not errors:
                return None
            error = errors[0]
            if str(error) == 'This field is required.':
                return f"The field '{field_path}' is required" if field_path else 'A required field is missing'
            return str(error)
        elif errors:
            return str(errors)
        return None
