from django.utils.translation import gettext_lazy as _


class ConditionalLogicEngine:
    """Engine for evaluating conditional visibility logic on survey sections and fields."""

    def evaluate_operator(self, operator, field_value, condition_value):
        """Evaluate a single operator against field_value and condition_value. Returns bool."""
        if operator == 'eq':
            return field_value == condition_value
        if operator == 'neq':
            return field_value != condition_value
        if operator == 'gt':
            try:
                return float(field_value) > float(condition_value)
            except (ValueError, TypeError):
                return False
        if operator == 'lt':
            try:
                return float(field_value) < float(condition_value)
            except (ValueError, TypeError):
                return False
        if operator == 'gte':
            try:
                return float(field_value) >= float(condition_value)
            except (ValueError, TypeError):
                return False
        if operator == 'lte':
            try:
                return float(field_value) <= float(condition_value)
            except (ValueError, TypeError):
                return False
        if operator == 'contains':
            try:
                return condition_value in field_value
            except (TypeError, AttributeError):
                return False
        if operator == 'in':
            try:
                return field_value in condition_value
            except (TypeError, AttributeError):
                return False
        # Unknown operator
        return False

    def evaluate(self, conditions, answers):
        """
        Evaluate all conditions against current answers. Args: conditions (raw JSONField value),
        answers (dict of {str(field_id): value}). Returns bool — True if visible, False if hidden.
        """
        # Null or missing conditions → always visible
        if not conditions:
            return True

        condition_list = conditions.get('conditions')

        # Empty or missing list → always visible
        if not condition_list:
            return True

        # ALL conditions must pass (AND logic)
        for condition in condition_list:
            field_id = str(condition.get('field_id', ''))
            operator = condition.get('operator', '')
            condition_value = condition.get('value')

            field_value = answers.get(field_id)

            # Field not answered → condition fails
            if field_value is None:
                return False

            if not self.evaluate_operator(operator, field_value, condition_value):
                return False

        return True

    def get_active_fields(self, survey, answers):
        """
        Return ordered list of Field instances whose conditions pass given current answers.
        Args: survey (Survey model instance), answers (dict of {str(field_id): value}).
        Returns list of active Field instances.
        """
        active_fields = []

        sections = survey.sections.order_by('order').prefetch_related('fields')

        for section in sections:
            # Skip entire section if its conditions fail
            if not self.evaluate(section.conditions, answers):
                continue

            for field in section.fields.order_by('order'):
                if self.evaluate(field.conditions, answers):
                    active_fields.append(field)

        return active_fields
