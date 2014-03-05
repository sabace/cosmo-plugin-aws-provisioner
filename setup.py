from setuptools import setup

COSMO_CELERY_VERSION = "0.3"
COSMO_CELERY_BRANCH = "develop"
COSMO_CELERY = "https://github.com/CloudifySource/" \
               "cosmo-celery-common/tarball/{0}".format(COSMO_CELERY_BRANCH)


setup(
    zip_safe=True,
    name='cloudify-aws-plugin',
    version='0.1.0',
    packages=[
        'cosmo_aws_plugin'
    ],
    license='LICENSE',
    description='Cloudify plugin for Amazon Web Services Elastic Cloud Compute(EC2).',
    install_requires=[
        "celery",
        "boto"
    ],
    dependency_links=["{0}#egg=cosmo-celery-common-{1}"
                      .format(COSMO_CELERY, COSMO_CELERY_VERSION)]
)
