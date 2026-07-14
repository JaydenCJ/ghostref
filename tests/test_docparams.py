"""Documented-parameter checks across Google, Sphinx, and NumPy dialects."""

import textwrap

from ghostref.docparams import check_docstring_params


def check(source):
    return check_docstring_params(textwrap.dedent(source), "f.py")


def test_google_style_stale_parameter_is_flagged():
    findings = check(
        '''
        def reserve(sku, quantity):
            """Reserve stock.

            Args:
                sku: The product.
                count: Renamed to quantity long ago.
            """
        '''
    )
    assert [finding.token for finding in findings] == ["count"]
    assert findings[0].kind == "param"
    assert "'reserve'" in findings[0].message


def test_google_style_current_parameters_pass():
    findings = check(
        '''
        def reserve(sku, quantity=1):
            """Reserve stock.

            Args:
                sku (str): The product.
                quantity (int): Units to hold, described over
                    a continuation line with colons: like this.
            """
        '''
    )
    assert findings == []


def test_sphinx_param_fields_are_checked():
    findings = check(
        '''
        def send(address):
            """Deliver.

            :param address: Where to send.
            :param str payload: Removed in the rewrite.
            """
        '''
    )
    assert [finding.token for finding in findings] == ["payload"]


def test_numpy_style_sections_are_checked():
    findings = check(
        '''
        def fit(data, epochs):
            """Train.

            Parameters
            ----------
            data : array
                Training rows.
            learning_rate : float
                Gone since the optimizer change.
            """
        '''
    )
    assert [finding.token for finding in findings] == ["learning_rate"]


def test_functions_with_kwargs_are_skipped_entirely():
    # **kwargs can absorb any documented name; flagging would be noise.
    findings = check(
        '''
        def call(url, **kwargs):
            """Args:
                timeout: Passed through to the transport.
            """
        '''
    )
    assert findings == []


def test_star_args_names_and_self_are_accepted():
    findings = check(
        '''
        class C:
            def run(self, *jobs):
                """Args:
                    self: The instance.
                    jobs: What to run.
                """
        '''
    )
    assert findings == []


def test_finding_points_at_the_documenting_line():
    findings = check(
        '''
        def f(a):
            """Doc.

            Args:
                a: Fine.
                gone: Stale.
            """
        '''
    )
    (finding,) = findings
    # line 7 of the dedented source is "        gone: Stale."
    assert finding.line == 7
    assert "gone:" in finding.context


def test_close_typo_gets_a_suggestion():
    findings = check(
        '''
        def f(quantity):
            """Args:
                quantiy: Typo for quantity.
            """
        '''
    )
    assert findings[0].suggestion == "quantity"


def test_ignore_marker_suppresses_the_whole_docstring():
    findings = check(
        '''
        def f(a):
            """Args:
                gone: Stale but accepted. ghostref: ignore
            """
        '''
    )
    assert findings == []
