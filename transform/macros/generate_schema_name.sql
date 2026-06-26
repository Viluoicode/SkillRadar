{#-
  Force every model into the target schema (`main`) instead of dbt's default
  `<target_schema>_<custom_schema>` concatenation. This keeps the marts at their bare names —
  e.g. `main.skill_demand` — so the serving read model (which queries unqualified table names)
  reads exactly what dbt builds. The cutover therefore needs no change to repositories.py.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema }}
{%- endmacro %}
