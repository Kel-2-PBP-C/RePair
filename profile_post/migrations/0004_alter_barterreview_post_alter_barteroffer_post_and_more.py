import django.db.models.deletion
from django.core.management.color import no_style
from django.db import migrations, models


PLACEHOLDER_IMAGE = (
    'https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item'
)


def move_posts_to_barters(apps, schema_editor):
    Post = apps.get_model('profile_post', 'Post')
    Barter = apps.get_model('barter_details', 'Barter')
    Offer = apps.get_model('profile_post', 'BarterOffer')
    Review = apps.get_model('profile_post', 'BarterReview')
    database = schema_editor.connection.alias
    post_ids = {}

    for post in Post.objects.using(database).all().iterator():
        barter = Barter.objects.using(database).create(
            owner_id=post.user_id,
            thumbnail=post.image_url or PLACEHOLDER_IMAGE,
            title=post.title,
            description=post.description,
            condition=post.condition,
            condition_percentage=None,
            shipping_method=post.shipping_duration,
            status=post.status,
            item_year=None,
            item_replacement=post.preferred_barter,
            item_location=post.location,
            location_code=post.location_code,
            category=post.category,
            completed_at=post.completed_at,
            is_profile_post=True,
            legacy_profile_post_id=post.pk,
        )
        Barter.objects.using(database).filter(pk=barter.pk).update(
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
        post_ids[post.pk] = barter.pk

    for post_id, barter_id in post_ids.items():
        Offer.objects.using(database).filter(post_id=post_id).update(
            barter_id=barter_id
        )
        Review.objects.using(database).filter(post_id=post_id).update(
            barter_id=barter_id
        )


def restore_posts(apps, schema_editor):
    Post = apps.get_model('profile_post', 'Post')
    Barter = apps.get_model('barter_details', 'Barter')
    Offer = apps.get_model('profile_post', 'BarterOffer')
    Review = apps.get_model('profile_post', 'BarterReview')
    database = schema_editor.connection.alias
    connection = schema_editor.connection

    for barter in Barter.objects.using(database).filter(is_profile_post=True).iterator():
        values = {
            'user_id': barter.owner_id,
            'title': barter.title,
            'description': barter.description,
            'image_url': barter.thumbnail,
            'location': barter.item_location,
            'condition': barter.condition,
            'shipping_duration': barter.shipping_method,
            'status': barter.status,
            'preferred_barter': barter.item_replacement,
            'location_code': barter.location_code,
            'category': barter.category,
            'completed_at': barter.completed_at,
        }
        if barter.legacy_profile_post_id is not None:
            values['id'] = barter.legacy_profile_post_id
        post = Post.objects.using(database).create(**values)
        Post.objects.using(database).filter(pk=post.pk).update(
            created_at=barter.created_at,
            updated_at=barter.updated_at,
        )
        Offer.objects.using(database).filter(barter_id=barter.pk).update(
            post_id=post.pk
        )
        Review.objects.using(database).filter(barter_id=barter.pk).update(
            post_id=post.pk
        )

    sequence_sql = connection.ops.sequence_reset_sql(
        no_style(),
        [Post],
    )
    with connection.cursor() as cursor:
        for statement in sequence_sql:
            cursor.execute(statement)


class Migration(migrations.Migration):

    dependencies = [
        ('barter_details', '0008_barter_category_barter_completed_at_and_more'),
        ('profile_post', '0003_post_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='barteroffer',
            name='post',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='offers',
                to='profile_post.post',
            ),
        ),
        migrations.AlterField(
            model_name='barterreview',
            name='post',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reviews',
                to='profile_post.post',
            ),
        ),
        migrations.AddField(
            model_name='barteroffer',
            name='barter',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='offers',
                to='barter_details.barter',
            ),
        ),
        migrations.AddField(
            model_name='barterreview',
            name='barter',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reviews',
                to='barter_details.barter',
            ),
        ),
        migrations.RunPython(move_posts_to_barters, restore_posts),
        migrations.RemoveConstraint(
            model_name='barterreview',
            name='unique_review_per_role',
        ),
        migrations.RemoveField(
            model_name='barteroffer',
            name='post',
        ),
        migrations.RemoveField(
            model_name='barterreview',
            name='post',
        ),
        migrations.RenameField(
            model_name='barteroffer',
            old_name='barter',
            new_name='post',
        ),
        migrations.RenameField(
            model_name='barterreview',
            old_name='barter',
            new_name='post',
        ),
        migrations.AlterField(
            model_name='barteroffer',
            name='post',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='offers',
                to='barter_details.barter',
            ),
        ),
        migrations.AlterField(
            model_name='barterreview',
            name='post',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='reviews',
                to='barter_details.barter',
            ),
        ),
        migrations.AddConstraint(
            model_name='barterreview',
            constraint=models.UniqueConstraint(
                fields=('post', 'role'),
                name='unique_review_per_role',
            ),
        ),
        migrations.DeleteModel(
            name='Post',
        ),
    ]
