from flask import request
from marshmallow import Schema, fields, validate, EXCLUDE


def parse_body(schema_class):
    """Carica e valida il body JSON della request con lo schema dato.
    Lancia marshmallow.ValidationError se la validazione fallisce."""
    return schema_class().load(request.get_json() or {})


class UpsertUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)
    name = fields.Str(load_default="")
    surname = fields.Str(load_default="")
    profile_image = fields.Str(load_default="")


class CreateUserSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1))
    surname = fields.Str(load_default="")
    email = fields.Email(required=True)
    profile_image = fields.Str(load_default=None, allow_none=True)
    paid_list_shown = fields.Bool(load_default=True)
    is_guest = fields.Bool(load_default=False)


class CreateExpenseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1))
    amount = fields.Decimal(required=True, places=2, validate=validate.Range(min=0))
    expense_owner_user_id = fields.Int(required=True)
    expense_list_id = fields.Int(required=True)
    expense_date = fields.Str(required=True, validate=validate.Length(min=1))
    expense_type_id = fields.Int(load_default=None, allow_none=True)


class CreateExpensesListSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1))
    user_id = fields.Int(required=True)
    paid = fields.Bool(load_default=False)
    list_type = fields.Str(load_default="shared")


class CreateShoppingListSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1))
    owner_id = fields.Int(required=True)
    list_type = fields.Str(load_default="personal")
    completed = fields.Bool(load_default=False)


class CreateShoppingItemSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    shopping_list_id = fields.Int(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=1))
    quantity = fields.Int(load_default=1, validate=validate.Range(min=1))
    checked = fields.Bool(load_default=False)
    sort_order = fields.Int(load_default=0)
    category_id = fields.Int(load_default=None, allow_none=True)


class CreateShoppingCategorySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    shopping_list_id = fields.Int(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=1))
    parent_id = fields.Int(load_default=None, allow_none=True)
    sort_order = fields.Int(load_default=0)
