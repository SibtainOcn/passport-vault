from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('vault','0001_initial')]
    operations=[
        migrations.AddField(model_name='workbook',name='name',field=models.CharField(default='Master Excel',max_length=200)),
        migrations.AddField(model_name='workbook',name='active',field=models.BooleanField(db_index=True,default=False)),
        migrations.AddField(model_name='workbook',name='config',field=models.JSONField(default=dict)),
    ]
