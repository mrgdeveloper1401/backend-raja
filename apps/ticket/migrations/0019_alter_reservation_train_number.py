import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ticket", "0018_reservationattempt_find_trains"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE "reservations"
                ALTER COLUMN "train_number" TYPE varchar(10)[]
                USING (
                    CASE
                        WHEN "train_number" IS NULL THEN NULL
                        ELSE ARRAY["train_number"::text]
                    END
                );
            """,
            state_operations=[
                migrations.AlterField(
                    model_name="reservation",
                    name="train_number",
                    field=django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=10),
                        blank=True,
                        default=list,
                        help_text="لیستی از شماره قطارهای مجاز برای رزرو",
                        null=True,
                    ),
                ),
            ],
        ),
    ]
