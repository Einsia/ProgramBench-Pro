"""Item types of the pinned product's global schema (version 44): fields in schema order, creator types (the
primary one first) and base-field mappings. Fixture inputs only; checks never read them as expectations."""

SCHEMA_VERSION = 44

TYPES = {
    'annotation': {
        'fields': [],
        'creators': [],
        'base': {}},
    'artwork': {
        'fields': ['title', 'abstractNote', 'artworkMedium', 'artworkSize', 'date', 'eventPlace', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['artist', 'contributor'],
        'base': {'artworkMedium': 'medium'}},
    'attachment': {
        'fields': ['title', 'accessDate', 'url'],
        'creators': [],
        'base': {}},
    'audioRecording': {
        'fields': ['title', 'abstractNote', 'audioRecordingFormat', 'seriesTitle', 'volume', 'numberOfVolumes', 'label', 'place', 'date', 'runningTime', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['performer', 'originalCreator', 'composer', 'wordsBy', 'translator', 'contributor'],
        'base': {'audioRecordingFormat': 'medium', 'label': 'publisher'}},
    'bill': {
        'fields': ['title', 'abstractNote', 'billNumber', 'code', 'codeVolume', 'section', 'codePages', 'legislativeBody', 'session', 'history', 'date', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['sponsor', 'cosponsor', 'contributor'],
        'base': {'billNumber': 'number', 'codeVolume': 'volume', 'codePages': 'pages', 'legislativeBody': 'authority'}},
    'blogPost': {
        'fields': ['title', 'abstractNote', 'blogTitle', 'websiteType', 'date', 'DOI', 'citationKey', 'url', 'accessDate', 'ISSN', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'translator', 'commenter', 'contributor'],
        'base': {'blogTitle': 'publicationTitle', 'websiteType': 'type'}},
    'book': {
        'fields': ['title', 'abstractNote', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'date', 'publisher', 'place', 'originalDate', 'originalPublisher', 'originalPlace', 'format', 'numPages', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'seriesEditor'],
        'base': {'format': 'medium'}},
    'bookSection': {
        'fields': ['title', 'abstractNote', 'bookTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'date', 'publisher', 'place', 'originalDate', 'originalPublisher', 'originalPlace', 'format', 'pages', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'bookAuthor', 'translator', 'seriesEditor'],
        'base': {'bookTitle': 'publicationTitle', 'format': 'medium'}},
    'case': {
        'fields': ['caseName', 'abstractNote', 'court', 'dateDecided', 'docketNumber', 'reporter', 'reporterVolume', 'firstPage', 'history', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'counsel', 'contributor'],
        'base': {'caseName': 'title', 'court': 'authority', 'dateDecided': 'date', 'docketNumber': 'number', 'reporterVolume': 'volume', 'firstPage': 'pages'}},
    'computerProgram': {
        'fields': ['title', 'abstractNote', 'seriesTitle', 'versionNumber', 'date', 'system', 'company', 'place', 'programmingLanguage', 'rights', 'citationKey', 'url', 'accessDate', 'DOI', 'ISBN', 'archive', 'archiveLocation', 'libraryCatalog', 'callNumber', 'shortTitle', 'extra'],
        'creators': ['programmer', 'contributor'],
        'base': {'company': 'publisher'}},
    'conferencePaper': {
        'fields': ['title', 'abstractNote', 'proceedingsTitle', 'conferenceName', 'publisher', 'place', 'date', 'eventPlace', 'volume', 'issue', 'numberOfVolumes', 'pages', 'series', 'seriesNumber', 'DOI', 'ISBN', 'citationKey', 'url', 'accessDate', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'seriesEditor'],
        'base': {'proceedingsTitle': 'publicationTitle'}},
    'dataset': {
        'fields': ['title', 'abstractNote', 'identifier', 'type', 'versionNumber', 'date', 'repository', 'repositoryLocation', 'format', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor'],
        'base': {'identifier': 'number', 'repository': 'publisher', 'repositoryLocation': 'place', 'format': 'medium'}},
    'dictionaryEntry': {
        'fields': ['title', 'abstractNote', 'dictionaryTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'date', 'publisher', 'place', 'pages', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'seriesEditor'],
        'base': {'dictionaryTitle': 'publicationTitle'}},
    'document': {
        'fields': ['title', 'abstractNote', 'type', 'date', 'publisher', 'place', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'reviewedAuthor'],
        'base': {}},
    'email': {
        'fields': ['subject', 'abstractNote', 'date', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'translator', 'contributor', 'recipient'],
        'base': {'subject': 'title'}},
    'encyclopediaArticle': {
        'fields': ['title', 'abstractNote', 'encyclopediaTitle', 'series', 'seriesNumber', 'volume', 'numberOfVolumes', 'edition', 'date', 'publisher', 'place', 'pages', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'seriesEditor'],
        'base': {'encyclopediaTitle': 'publicationTitle'}},
    'film': {
        'fields': ['title', 'abstractNote', 'distributor', 'place', 'date', 'genre', 'videoRecordingFormat', 'runningTime', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['director', 'producer', 'scriptwriter', 'castMember', 'host', 'guest', 'narrator', 'translator', 'contributor'],
        'base': {'distributor': 'publisher', 'genre': 'type', 'videoRecordingFormat': 'medium'}},
    'forumPost': {
        'fields': ['title', 'abstractNote', 'forumTitle', 'postType', 'date', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'contributor'],
        'base': {'forumTitle': 'publicationTitle', 'postType': 'type'}},
    'hearing': {
        'fields': ['title', 'abstractNote', 'committee', 'publisher', 'numberOfVolumes', 'documentNumber', 'pages', 'legislativeBody', 'session', 'history', 'date', 'place', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['contributor'],
        'base': {'documentNumber': 'number', 'legislativeBody': 'authority'}},
    'instantMessage': {
        'fields': ['title', 'abstractNote', 'date', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'recipient'],
        'base': {}},
    'interview': {
        'fields': ['title', 'abstractNote', 'interviewMedium', 'date', 'publisher', 'place', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['interviewee', 'contributor', 'interviewer', 'translator'],
        'base': {'interviewMedium': 'medium'}},
    'journalArticle': {
        'fields': ['title', 'abstractNote', 'publicationTitle', 'publisher', 'place', 'date', 'volume', 'issue', 'section', 'partNumber', 'partTitle', 'pages', 'series', 'seriesTitle', 'seriesText', 'journalAbbreviation', 'DOI', 'citationKey', 'url', 'accessDate', 'PMID', 'PMCID', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'reviewedAuthor'],
        'base': {}},
    'letter': {
        'fields': ['title', 'abstractNote', 'letterType', 'date', 'eventPlace', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'recipient', 'contributor', 'translator'],
        'base': {'letterType': 'type'}},
    'magazineArticle': {
        'fields': ['title', 'abstractNote', 'publicationTitle', 'publisher', 'place', 'date', 'volume', 'issue', 'pages', 'ISSN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'translator', 'reviewedAuthor'],
        'base': {}},
    'manuscript': {
        'fields': ['title', 'abstractNote', 'manuscriptType', 'institution', 'place', 'date', 'numPages', 'number', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'translator'],
        'base': {'manuscriptType': 'type', 'institution': 'publisher'}},
    'map': {
        'fields': ['title', 'abstractNote', 'mapType', 'scale', 'seriesTitle', 'edition', 'publisher', 'place', 'date', 'DOI', 'ISBN', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['cartographer', 'contributor', 'seriesEditor'],
        'base': {'mapType': 'type'}},
    'newspaperArticle': {
        'fields': ['title', 'abstractNote', 'publicationTitle', 'publisher', 'place', 'date', 'volume', 'issue', 'edition', 'section', 'pages', 'ISSN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'translator', 'reviewedAuthor'],
        'base': {}},
    'note': {
        'fields': [],
        'creators': [],
        'base': {}},
    'patent': {
        'fields': ['title', 'abstractNote', 'place', 'country', 'assignee', 'issuingAuthority', 'patentNumber', 'filingDate', 'pages', 'applicationNumber', 'priorityNumbers', 'issueDate', 'priorityDate', 'references', 'legalStatus', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['inventor', 'attorneyAgent', 'contributor'],
        'base': {'issuingAuthority': 'authority', 'patentNumber': 'number', 'issueDate': 'date', 'priorityDate': 'originalDate', 'legalStatus': 'status'}},
    'podcast': {
        'fields': ['title', 'abstractNote', 'seriesTitle', 'episodeNumber', 'audioFileType', 'date', 'publisher', 'place', 'runningTime', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['podcaster', 'guest', 'producer', 'executiveProducer', 'seriesCreator', 'director', 'scriptwriter', 'castMember', 'translator', 'contributor'],
        'base': {'episodeNumber': 'number', 'audioFileType': 'medium'}},
    'preprint': {
        'fields': ['title', 'abstractNote', 'genre', 'repository', 'archiveID', 'place', 'date', 'series', 'seriesNumber', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'editor', 'translator', 'reviewedAuthor'],
        'base': {'genre': 'type', 'repository': 'publisher', 'archiveID': 'number'}},
    'presentation': {
        'fields': ['title', 'abstractNote', 'presentationType', 'date', 'meetingName', 'place', 'series', 'sessionTitle', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['presenter', 'chair', 'organizer', 'contributor', 'translator'],
        'base': {'presentationType': 'type', 'sessionTitle': 'publicationTitle'}},
    'radioBroadcast': {
        'fields': ['title', 'abstractNote', 'programTitle', 'episodeNumber', 'audioRecordingFormat', 'network', 'place', 'date', 'runningTime', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['creator', 'host', 'guest', 'producer', 'executiveProducer', 'seriesCreator', 'director', 'scriptwriter', 'castMember', 'translator', 'contributor'],
        'base': {'programTitle': 'publicationTitle', 'episodeNumber': 'number', 'audioRecordingFormat': 'medium', 'network': 'publisher'}},
    'report': {
        'fields': ['title', 'abstractNote', 'reportNumber', 'reportType', 'institution', 'place', 'date', 'seriesTitle', 'seriesNumber', 'pages', 'DOI', 'ISBN', 'citationKey', 'url', 'accessDate', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'editor', 'contributor', 'translator', 'seriesEditor'],
        'base': {'reportNumber': 'number', 'reportType': 'type', 'institution': 'publisher'}},
    'standard': {
        'fields': ['title', 'abstractNote', 'organization', 'committee', 'type', 'number', 'versionNumber', 'edition', 'status', 'date', 'publisher', 'place', 'partNumber', 'partTitle', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'numPages', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'editor', 'contributor'],
        'base': {'organization': 'authority'}},
    'statute': {
        'fields': ['nameOfAct', 'abstractNote', 'code', 'codeNumber', 'publicLawNumber', 'dateEnacted', 'pages', 'section', 'session', 'history', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'contributor'],
        'base': {'nameOfAct': 'title', 'publicLawNumber': 'number', 'dateEnacted': 'date'}},
    'thesis': {
        'fields': ['title', 'abstractNote', 'thesisType', 'university', 'place', 'date', 'series', 'seriesNumber', 'numPages', 'DOI', 'ISBN', 'citationKey', 'url', 'accessDate', 'ISSN', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['author', 'contributor'],
        'base': {'thesisType': 'type', 'university': 'publisher'}},
    'tvBroadcast': {
        'fields': ['title', 'abstractNote', 'programTitle', 'episodeNumber', 'videoRecordingFormat', 'network', 'place', 'date', 'runningTime', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['director', 'producer', 'executiveProducer', 'seriesCreator', 'scriptwriter', 'castMember', 'host', 'guest', 'narrator', 'translator', 'contributor'],
        'base': {'programTitle': 'publicationTitle', 'episodeNumber': 'number', 'videoRecordingFormat': 'medium', 'network': 'publisher'}},
    'videoRecording': {
        'fields': ['title', 'abstractNote', 'videoRecordingFormat', 'seriesTitle', 'volume', 'numberOfVolumes', 'studio', 'place', 'date', 'runningTime', 'ISBN', 'DOI', 'citationKey', 'url', 'accessDate', 'archive', 'archiveLocation', 'shortTitle', 'language', 'libraryCatalog', 'callNumber', 'rights', 'extra'],
        'creators': ['creator', 'director', 'producer', 'scriptwriter', 'executiveProducer', 'castMember', 'host', 'guest', 'narrator', 'translator', 'contributor'],
        'base': {'videoRecordingFormat': 'medium', 'studio': 'publisher'}},
    'webpage': {
        'fields': ['title', 'abstractNote', 'websiteTitle', 'websiteType', 'date', 'publisher', 'place', 'DOI', 'citationKey', 'url', 'accessDate', 'shortTitle', 'language', 'rights', 'extra'],
        'creators': ['author', 'contributor', 'translator'],
        'base': {'websiteTitle': 'publicationTitle', 'websiteType': 'type'}},
}

REGULAR = [name for name in TYPES if name not in ('annotation', 'attachment', 'note')]
