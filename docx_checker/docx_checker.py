"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources


import hashlib
import logging
import mimetypes
import os

from docx import Document

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String
from xblock.fragment import Fragment
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt

from student.models import user_by_anonymous_id
from submissions import api as submissions_api
from submissions.models import StudentItem as SubmissionsStudent

from functools import partial
from webob.response import Response


from .utils import (
    load_resource,
    render_template,
    load_resources,
    )


from analyze import *


log = logging.getLogger(__name__)
BLOCK_SIZE = 8 * 1024

class DocxCheckerXBlock(XBlock):

    correct_docx_path = String(
         default='', scope=Scope.settings,
         help='Correct file from teacher',
        )

    source_docx_path = String(
         default='', scope=Scope.settings,
         help='Unformatted file for student',
        )

    student_docx_path = String(
         default='', scope=Scope.settings,
         help='Correct file from student',
        )

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        context = {
            "download_file": self.source_docx_path
        }

        fragment = Fragment()
        fragment.add_content(
            render_template(
                "static/html/docx_checker.html",
                context
            )
        )

        js_urls = (
            "static/js/src/docx_checker.js",
            )

        css_urls = (
            "static/css/docx_checker.css",
            )

        load_resources(js_urls, css_urls, fragment)

        fragment.initialize_js('DocxCheckerXBlock')
        return fragment

    def studio_view(self, context=None):
        fragment = Fragment()
        fragment.add_content(
            render_template(
                "static/html/docx_checker_studio.html",
                context
            )
        )

        js_urls = (
            "static/js/src/docx_checker_studio.js",
            )

        css_urls = (
            "static/css/docx_checker_studio.css",
            )

        load_resources(js_urls, css_urls, fragment)

        fragment.initialize_js('DocxCheckerXBlockEdit')
        return fragment

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("DocxCheckerXBlock",
             """<docx_checker/>
             """),
            ("Multiple DocxCheckerXBlock",
             """<vertical_demo>
                <docx_checker/>
                <docx_checker/>
                <docx_checker/>
                </vertical_demo>
             """),
        ]

    @XBlock.handler
    def download_assignment(self, request, suffix=''):
        path = _file_storage_path(
            self.location.to_deprecated_string(),
            self.uploaded_sha1,
            self.uploaded_filename
        )
        return self.download(
            path,
            self.uploaded_mimetype,
            self.uploaded_filename
        )

    def is_course_staff(self):
        # pylint: disable=no-member
        """
         Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    @XBlock.handler
    def upload_correct_file(self, request, suffix=''):
        upload = request.params['correctFile']
        sha1 = _get_sha1(upload.file)
        path = self._file_storage_path(sha1, upload.file.name)
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        self.correct_docx_path = path
        obj = get_analyze_the_document(self.correct_docx_path)
        return Response(json_body=obj)


    @XBlock.handler
    def upload_source_file(self, request, suffix=''):
        upload = request.params['sourceFile']
        sha1 = _get_sha1(upload.file)
        path = self._file_storage_path(sha1, upload.file.name)
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        self.source_docx_path = path

        return Response(json_body=str(path))

    def _file_storage_path(self, sha1, filename):
        # pylint: disable=no-member
        """
        Get file path of storage.
        """
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}'
            '/{sha1}{ext}'.format(
                loc=self.location,
                sha1=sha1,
                ext=os.path.splitext(filename)[1]
            )
        )
        return path


def _get_sha1(file_descriptor):
    """
    Get file hex digest (fingerprint).
    """
    sha1 = hashlib.sha1()
    for block in iter(partial(file_descriptor.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file_descriptor.seek(0)
    return sha1.hexdigest()


def student_submission_id(self, submission_id=None):
    # pylint: disable=no-member
    """
    Returns dict required by the submissions app for creating and
    retrieving submissions for a particular student.
    """
    if submission_id is None:
        submission_id = self.xmodule_runtime.anonymous_student_id
        assert submission_id != (
            'MOCK', "Forgot to call 'personalize' in test."
        )
    return {
        "student_id": submission_id,
        "course_id": self.course_id,
        "item_id": self.block_id,
        "item_type": 'sga',  # ???
    }
def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied