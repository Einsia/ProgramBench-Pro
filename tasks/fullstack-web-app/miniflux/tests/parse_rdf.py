"""RDF (RSS 1.0) parsing: items with Dublin Core dates, creators and subjects, encoded content, items identified
only by their about attribute, missing dates and relative links."""
import parse_json


def build(s):
    parse_json.build_rdf(s)
