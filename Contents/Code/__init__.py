import urllib
import calendar
from DumbTools import DumbKeyboard, DumbPrefs
NAME = 'SankakuComplex'
PREFIX = '/photos/sankakucomplex'
ICON = "sankaku-content-icon.png"
POSTS_API = 'https://chan.sankakucomplex.com/post/index.json'
LOGIN_URL = 'https://chan.sankakucomplex.com/user/authenticate'
POOLS_API = 'https://chan.sankakucomplex.com/pool/index.json?query={query}&page={page}'
# the date options to prompt the client with, excluding 'all time' which is always there
DATE_VIEWS = [1, 7, 30, 90, 180, 365]
TAG_LIMIT = 9
# list of tags to force onto every query
FORCED_TAGS = ['-animated', '-video']
BROKEN_CLIENTS = ['Plex Home Theater', "OpenPHT"]
EMPTY_SEARCH = '__empty__'
# sorting methods to prompt the client with
SORT_TAGS = ['order:popular', 'order:quality', 'order:rawscore', 'order:score',
             'order:viewcount', 'order:votecount', 'order:favcount']
ICONS = {"default": "sankaku-content-icon.png",
         "latest": "icon-latest.png",
         "saved": "icon-saved.png",
         "search": "icon-search.png",
         "pools": "icon-pools.png",
         "login": "icon-login.png",
         "logout": "icon-logout.png"}
            
def Start():
    ObjectContainer.title1 = NAME
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.User_Agent = ("Mozilla/5.0 (Windows NT 10.0; WOW64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/45.0.2454.101 Safari/537.36")
    Plugin.AddViewGroup("Details", viewMode="InfoList", mediaType="items")
    Plugin.AddViewGroup("Images", viewMode="PanelStream", mediaType="items")
    if 'search_history' not in Dict:
        Dict['search_history'] = {}
    if 'post_time' not in Dict:
        Dict['post_time'] = {}
    if 'page_thumbs' not in Dict:
        Dict['page_thumbs'] = {}
    if 'pool_thumbs' not in Dict:
        Dict['pool_thumbs'] = {}
    Dict.Save()

@handler(PREFIX, NAME, ICON)
def MainMenu():       
    oc = ObjectContainer(no_cache=True)
    if Dict['pass_hash']: # Logged in (we have a passhash to give to the server)
        # latest: get an album with an empty query
        oc.add(PhotoAlbumObject(key=Callback(Page, tags=process_query(), ignore_cache=True),
                                rating_key='latest', title=L('latest'), thumb=R(ICONS['latest'])))
        # Pools
        oc.add(DirectoryObject(key=Callback(Pools, query="all", page=1),
                               title=L('pools'), thumb=R(ICONS['pools'])))
        # search: prompt for a query
        search_title = u'%s (%d tags available)' % (L('search'), TAG_LIMIT-tags_used())
        if Client.Product in DumbKeyboard.clients:
            DumbKeyboard(PREFIX, oc, Search, dktitle=search_title, dkthumb=R(ICONS['search']))
        else:
            oc.add(InputDirectoryObject(key=Callback(Search), title=search_title,
                                        prompt='Search', thumb=R(ICONS['search'])))
        # saved searches: list previous searches
        oc.add(DirectoryObject(key=Callback(ListSearchHistory, action="view"),
                               title=L('savedsearch'), thumb=R(ICONS['saved'])))
        # manage searches: menu for managing saved searches
        oc.add(DirectoryObject(key=Callback(SearchManagerMenu),
                               title=L('managesearches'), thumb=R(ICONS['saved'])))

        oc.add(DirectoryObject(key=Callback(Logout),
                               title="Logout", thumb=R(ICONS['logout'])))
    else: # not logged in
        oc.add(DirectoryObject(key=Callback(Login),
                               title="Login", thumb=R(ICONS['login'])))
    # preferences
    if Client.Product in DumbPrefs.clients:
        DumbPrefs(PREFIX, oc)
    else:
        oc.add(PrefsObject(title=L('preferences')))
    return oc


def api_request(tags, limit=1, page=1, cache_time=None):
    """ make an api request, return JSON """
    params = {
        'login':         Prefs['username'].strip(),
        'password_hash': Dict['pass_hash'],
        'limit':         limit,
        'page':          page,
        'tags':          tags.strip()}
    try:
        return JSON.ObjectFromURL(POSTS_API + "?" + urllib.urlencode(params), cacheTime=cache_time)
    except Exception:
        return []


def error_message(error, message):
    return ObjectContainer(header=u'%s' % error,
                           message=u'%s' % message)


def get_thumbnail(query):
    """ make a limit=1 request to grab a thumbnail to use for a query """
    try:
        posts = api_request(tags=query.strip(), limit=1, page=1)
        return 'https:' + posts[0]['preview_url']
    except Exception:
        return ""


def set_pool_thumb(pool_id, url):
    """ set the thumb url for the given pool id """
    if pool_id not in Dict['pool_thumbs']:
        Dict['pool_thumbs'][pool_id] = url
        Dict.Save()


def set_page_thumb(tags, page, url):
    """ set the thumb url for the given tags and page number """
    if tags not in Dict['page_thumbs']:
        Dict['page_thumbs'][tags] = {}
    if page not in Dict['page_thumbs'][tags]:
        Dict['page_thumbs'][tags][page] = url
        Dict.Save()


def get_page_thumb(tags, page):
    """ get the thumb url for the given tags and page number """
    if tags in Dict['page_thumbs']:
        if page in Dict['page_thumbs'][tags]:
            return Dict['page_thumbs'][tags][page]
    return None


def add_tag(current, new, separator=" "):
    """ add new to current with proper spacing when needed.
    plex doesn't like passing lists around, so its a space separated string
    """
    return current + new if not len(current) else current + separator + new


def tag_type(id_number):
    """ strings for tag types """
    return {
        0: 'general',
        1: 'artist',
        2: 'studio',
        3: 'copyright', # - original, touhou, vocaloid, ...
        4: 'character',
        8: 'medium',    # - resolution, aspect ratio, wallpaper, comic, ...
        9: 'meta',      # - tag_me, ...
    }[id_number]


def tag_icon(tag_type_string):
    """ get a unicode icon for tag types """
    return {
        'general':   '⚑',
        'artist':    '✐',
        'studio':    '™',
        'copyright': '©',
        'character': '☻',
        'medium':    '◪',
        'meta':      '☸',
    }[tag_type_string]


def parse_tags(tags):
    """ parse tags into a usable dictionary """
    post_tags = {}
    for tag in tags:
        if tag_type(tag['type']) not in post_tags:
            post_tags[tag_type(tag['type'])] = []
        post_tags[tag_type(tag['type'])].append(tag)
    return post_tags


def tags_used():
    """ return the number of tags being used by the system and in preferences.
    api limits to TAG_LIMIT max tags
    """
    count = 0
    add_tags = len(Prefs['add_tags'].split()) if Prefs['add_tags'] else 0
    rem_tags = len(Prefs['remove_tags'].split()) if Prefs['remove_tags'] else 0
    count += (add_tags + rem_tags) if Prefs['globals_enabled'] else 0
    count += len(FORCED_TAGS) + 1
    count += 1 if Prefs['threshold_enabled'] else 0
    return count


def make_date_tag(dt1, dt2, month=False):
    """ make a date tag from 2 datetimes.
    month=True will use the first day of the month of the DTs.
    """
    t = '%Y-%m-01' if month else '%Y-%m-%d'
    return "date:%s...%s" % (dt1.strftime(t), dt2.strftime(t))


def process_query(query=""):
    """ given a users query, add the stuff from prefs """
    if query is None:
        query = ""
    # add rating tag if set in prefs
    if Prefs['rating'] != "all":
        query = add_tag(query, Prefs['rating'])
    if Prefs['globals_enabled']:
        # Global remove tags
        if Prefs['remove_tags']:
            remove_tags = Prefs['remove_tags'].split()
            for tag in remove_tags:
                query = add_tag(query, "-"+tag)
        # Global add tags
        if Prefs['add_tags']:
            add_tags = Prefs['add_tags'].split()
            for tag in add_tags:
                query = add_tag(query, tag)
    # Forced tags (hardcoded for compatibility reasons)
    for tag in FORCED_TAGS:
        query = add_tag(query, tag)
    if Prefs['threshold_enabled']:
        # Global score threshold
        tags = query.split()
        score = False
        for tag in tags:
            if tag.startswith("score:"):
                score = True
                break
        if 'order:score' in tags or 'order:rawscore' in tags:
            score = True
        # add it
        if not score:
            if int(Prefs['score_threshold']) != 0:
                query = add_tag(query, "score:>%s" % Prefs['score_threshold'])
    return query

####################################################################################################
@route(PREFIX + '/login')
def Login():
    """ we need the salted hash to make api requests.
    Only way to get it is by logging in and reading the cookie
    """
    if not Prefs['username'] or not Prefs['password']:
        error_message(error="Login", message="Username or password is blank. Check settings.")
    payload = {'url': "",
               'user[name]': Prefs['username'].strip(),
               'user[password]': Prefs['password'].strip(),
               'commit': 'Login'}
    headers = {'origin':  'https://chan.sankakucomplex.com',
               'referer': 'https://chan.sankakucomplex.com/user/login'}
    try:
        HTTP.Request(url=LOGIN_URL, headers=headers, values=payload)
    except Exception:
        return error_message(error="Login", message=L('login_error'))
    try:
        pattern = Regex('pass_hash=([^;]*)')
        Dict['pass_hash'] = pattern.search(HTTP.CookiesForURL(LOGIN_URL)).group(1)
        Dict.Save()
        return error_message(error="Login", message=L('login_success') % Dict['pass_hash'])
    except Exception:
        return error_message(error="Login", message=L('login_passhash'))


@route(PREFIX + '/logout')
def Logout():
    """ clear the pass hash from dict """
    Dict['pass_hash'] = None
    return error_message(error="Logout", message=L('logout'))


@route(PREFIX + '/pools/list', page=int)
def Pools(query="", page=1):
    """ List pools """
    search = "" if query is None or query == "all" else query
    oc = ObjectContainer()
    pools = JSON.ObjectFromURL(POOLS_API.format(query=search, page=page),
                               cacheTime=CACHE_1HOUR)
    skipped = 0
    for pool in pools:
        pool_count = int(pool['post_count'])
        # skip when theres 0 items in the pool
        if pool_count < 1:
            skipped += 1
            continue
        pool_name = pool['name']
        pool_id = pool['id']
        title = '%s (%d)' % (pool_name.replace("_", " "), pool_count)
        oc.add(pages_directory(
            title=u'%s' % title,
            query=" ", pool=pool_id, poolsize=pool_count,
            thumb=Dict['pool_thumbs'][pool_id] \
                  if pool_id in Dict['pool_thumbs'] else R(ICONS['default'])
        ))
    if len(oc) + skipped >= 20:
        oc.add(NextPageObject(key=Callback(Pools, query=query, page=page+1)))
    return oc


@route(PREFIX + '/search')
def Search(query):
    if query is None or query == "" or query == " " or query.lower() == "none":
        query = EMPTY_SEARCH
    query = query.strip()
    AddItemToSearchHistory(query) # add the search to history
    if query == EMPTY_SEARCH:
        query = "" # return empty search constant to actual empty string
    query = process_query(query) # add tags from preferences
    # check if query has sorting already, if so skip to the date menu
    for tag in query.split():
        if tag.startswith('order:'):
            return DateMenu(query=query)
    # go to the sorting menu
    return SortMenu(query=query)


@route(PREFIX + '/search/history/manage')
def SearchManagerMenu():
    oc = ObjectContainer(no_cache=True, no_history=True)
    oc.add(DirectoryObject(key=Callback(ListSearchHistory, action="remove"),
                           title=L('searchhistoryremove')))
    oc.add(DirectoryObject(key=Callback(ClearSearchHistory),
                           title=L('searchhistoryclear')))
    return oc


@route(PREFIX + '/search/history/list/{action}')
def ListSearchHistory(action):
    oc = ObjectContainer()
    for item in Dict['search_history']:
        if action == "remove":
            oc.add(DirectoryObject(
                key=Callback(SearchHistoryRemoveItem, item=item),
                title="{0}: {1}".format(L('remove'), item),
                thumb=Dict['search_history'][item]))
        elif action == "view":
            oc.add(DirectoryObject(
                key=Callback(Search, query=item),
                title=item,
                thumb=Dict['search_history'][item]))
    oc.objects.sort(key=lambda obj: obj.title)
    return oc


@route(PREFIX + '/search/history/clear')
def ClearSearchHistory():
    Dict['search_history'] = {}
    Dict.Save()
    return error_message('ClearSearchHistory', "cleared")


@route(PREFIX + '/search/history/remove/{item}')
def SearchHistoryRemoveItem(item):
    if item not in Dict['search_history']:
        return error_message(item, "not in search history")
    del Dict['search_history'][item]
    Dict.Save()
    return error_message(item, "removed from history")


def AddItemToSearchHistory(query):
    if query and query not in Dict['search_history']:
        Dict['search_history'][query] = get_thumbnail(query if query != EMPTY_SEARCH else ' ')
        Dict.Save()        


@route(PREFIX + '/sortmenu/{query}')
def SortMenu(query):
    """ let user select the sorting method """
    oc = ObjectContainer(title2=L('sorting'), no_history=True)
    oc.add(DirectoryObject(key=Callback(DateMenu, query=query),
                           title=u'%s' % L('no_sort')))
    for item in SORT_TAGS:
        oc.add(DirectoryObject(key=Callback(DateMenu, query=add_tag(query, item)),
                               title=u'%s' % "{0}".format(L(item))))
    return oc


@route(PREFIX + '/datemenu/{query}')
def DateMenu(query):
    """ let user select the time frame for the search """
    oc = ObjectContainer(title2=L('post_age'), no_history=True)
    now = Datetime.Now()
    # Add 'All Time' (ie: don't add a date tag)
    oc.add(pages_directory(title=L('date_all'), query=query))
    # Add date tags to the query for the preset intervals in DATE_VIEWS
    for day_count in DATE_VIEWS:
        day_string = L('date_day') if day_count <= 1 else L('date_days')
        title = "Last {0} {1}".format(day_count, day_string)
        date_tag = make_date_tag(now-Datetime.Delta(days=day_count), now)
        oc.add(pages_directory(title=title, query=add_tag(query, date_tag)))
    # Add 1-month ranges for the past 2 years
    for _ in range(1, 25):
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        title = '%s %s' % (now.strftime('%B'), now.year)
        date_tag = make_date_tag(
            now,
            now + Datetime.Delta(days=1 + days_in_month - \
                (0 if now.day < days_in_month else days_in_month)),
            month=True)
        oc.add(pages_directory(title=title, query=add_tag(query, date_tag)))
        # move back 1 month
        now = now - Datetime.Delta(
            days=now.day if now.day < days_in_month else days_in_month)
    return oc


def photo_album(title, query, page=1, pool=None, thumb=None):
    return PhotoAlbumObject(key=Callback(Page, tags=query, page=page, pool=pool),
                            rating_key=query, title=title, thumb=thumb)


def pages_directory(title, query, page=1, pool=None, poolsize=0, thumb=None):
    return DirectoryObject(key=Callback(Pages, tags=query, page=page, pool=pool, poolsize=poolsize),
                           title=title, thumb=thumb)


@route(PREFIX + '/pages', page=int, pool=int, poolsize=int)
def Pages(tags, page=1, pool=None, poolsize=0):
    if Client.Platform not in BROKEN_CLIENTS or (pool and poolsize <= int(Prefs['limit'])):
        return Page(tags=tags, page=page, pool=pool)
    else:
        oc = ObjectContainer(no_cache=True)
        if pool:
            # pool paging
            count = 0
            page_num = 1
            while count < poolsize:
                oc.add(photo_album(title="Page %d" % page_num,
                                   query=tags, page=page_num, pool=pool,
                                   thumb=get_page_thumb(tags="pool:%d" % pool,
                                                        page=page_num)))
                page_num += 1
                count += int(Prefs['limit'])
            return oc
        else:
            # normal search paging
            oc.add(photo_album(title="Page %d" % page,
                               query=tags, page=page, pool=pool,
                               thumb=get_page_thumb(tags=tags, page=page)))

            oc.add(NextPageObject(key=Callback(Pages, tags=tags, page=page+1, pool=pool)))
            return oc


@route(PREFIX + '/pics/{tags}/{page}', page=int, pool=int, ignore_cache=bool)
def Page(tags, page=1, pool=None, ignore_cache=False, title_format='name,rating,favs'):
    """ make the actual api request and parse into photos """
    oc = ObjectContainer(content="photo", view_group="Images")
    # Finalize the tags
    final_tags = tags
    if pool:
        final_tags = add_tag(final_tags, "pool:%d" % pool)
    tag_count = len(final_tags.split())
    if tag_count > TAG_LIMIT: # hard limit of 9 tags you can use in a query.
        return error_message(error="Query",
                             message="Too Many Tags. %d/%d used." % (tag_count, TAG_LIMIT))
    try:
        posts = api_request(tags=final_tags, page=page, limit=Prefs['limit'],
                            cache_time=0 if ignore_cache else HTTP.CacheTime)
    except Exception:
        return error_message(error="API Request", message="Error making the api request")
    for post in posts:
        post_file_url = 'https:'+post['file_url']
        post_sample_url = 'https:'+post['sample_url']
        post_thumbnail_url = 'https:'+post['preview_url']
        # get metadata we want to use
        pid = post['id']
        ptags = parse_tags(post['tags'])
        pscore = post['total_score']
        vc = post['vote_count']
        stars = float(pscore) / float(vc) if vc > 0 else None
        post_favs = post['fav_count']
        post_date = post['created_at']['s']
        # Decide which size of the image to use based on Prefs
        image = post_file_url if Prefs['imagesize'] else post_sample_url
        # store the first results thumbnails for use on directories
        if not len(oc):
            if pool:
                set_pool_thumb(pool, post_thumbnail_url)
                set_page_thumb(tags="pool:%d"%pool, page=page, url=post_thumbnail_url)
            else:
                set_page_thumb(tags=tags, page=page, url=post_thumbnail_url)
        # Build the summary
        summary = ""
        for ttype in ptags:
            if not ptags[ttype]:
                continue
            summary += "  ".join(
                [tag_icon(ttype) + x['name'] for x in ptags[ttype]])
            summary += "\n\n"
        # Things that we might want to put in the title
        title_elements = {
            'name': ptags['character'][0]['name'].replace("_", " ") \
                    if 'character' in ptags else str(pid),
            'rating': "★ {:.1f}".format(stars) if stars else "",
            'favs': "❤ {0}".format(post_favs)
        }
        oc.add(PhotoObject(
            url=image, summary=summary,
            title="  ".join([title_elements[x] for x in title_format.split(',')]),
            thumb=Resource.ContentsOfURLWithFallback(post_thumbnail_url)))
    # PHT will go into an infinite loop if you enter a slideshow with a NextPageObject
    if Client.Platform not in BROKEN_CLIENTS:
        if len(oc) >= int(Prefs['limit']):
            oc.add(NextPageObject(key=Callback(Page, tags=tags, page=page+1)))
    return oc
