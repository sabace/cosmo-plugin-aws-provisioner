
from setuptools import setup

COSMO_CELERY_VERSION = "0.3"
COSMO_CELERY_BRANCH = "develop"
COSMO_CELERY = "https://github.com/CloudifySource/" \
               "cosmo-celery-common/tarball/{0}".format(COSMO_CELERY_BRANCH)


setup(
    zip_safe=True,
    name='cloudify-aws-plugin',
    version='0.1.0',
    author='narenthirasamy',
    author_email='naren@cloudenablers.com',
    packages=[
        'aws_plugin_common',
	'ec2_plugin'
    ],
    license='LICENSE',
    description='Cloudify plugin for Amazon Web Services Elastic Cloud Compute(EC2).',
    install_requires=[
        "cosmo-celery-common",
        "boto"
    ],
    dependency_links=["{0}#egg=cosmo-celery-common-{1}"
                      .format(COSMO_CELERY, COSMO_CELERY_VERSION)]
)
