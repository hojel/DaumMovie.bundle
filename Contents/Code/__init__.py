# -*- coding: utf-8 -*-
# Daum Movie

import urllib, unicodedata

DAUM_MOVIE_SRCH   = "http://movie.daum.net/search.do?type=%s&q=%s"

DAUM_MOVIE_DETAIL = "http://m.movie.daum.net/data/movie/movie_info/detail.json?movieId=%s"
DAUM_MOVIE_CAST   = "http://m.movie.daum.net/data/movie/movie_info/cast_crew.json?pageNo=1&pageSize=100&movieId=%s"
DAUM_MOVIE_PHOTO  = "http://m.movie.daum.net/data/movie/photo/movie/list.json?pageNo=1&pageSize=100&id=%s"

DAUM_TV_DETAIL    = "http://m.movie.daum.net/data/movie/tv/detail.json?tvProgramId=%s"
DAUM_TV_DETAIL2   = "http://movie.daum.net/tv/detail/main.do?tvProgramId=%s"
DAUM_TV_CAST      = "http://m.movie.daum.net/data/movie/tv/cast_crew.json?pageNo=1&pageSize=100&tvProgramId=%s"
DAUM_TV_PHOTO     = "http://m.movie.daum.net/data/movie/photo/tv/list.json?pageNo=1&pageSize=100&id=%s"
DAUM_TV_EPISODE   = "http://m.movie.daum.net/m/tv/episode?tvProgramId=%s"

IMDB_TITLE_SRCH   = "http://www.google.com/search?q=site:imdb.com+%s"
TVDB_TITLE_SRCH   = "http://thetvdb.com/api/GetSeries.php?seriesname=%s"

RE_YEAR_IN_NAME   =  Regex('\((\d+)\)')
RE_MOVIE_ID       =  Regex("movieId=(\d+)")
RE_TV_ID          =  Regex("tvProgramId=(\d+)")
RE_PHOTO_SIZE     =  Regex("/C\d+x\d+/")
RE_IMDB_ID        =  Regex("/(tt\d+)/")

def Start():
  HTTP.CacheTime = CACHE_1WEEK
  HTTP.Headers['Accept'] = 'text/html, application/json'

####################################################################################################
def searchDaumMovie(cate, results, media, lang):
    media_name = media.show if cate == 'tv' else media.name
    media_name = unicodedata.normalize('NFKC', unicode(media_name)).strip()
    Log.Debug("search: %s %s" %(media_name, media.year))

    url = DAUM_MOVIE_SRCH % (cate, urllib.quote(media_name.encode('utf8')))
    html = HTML.ElementFromURL( url )

    items = html.xpath('//span[@class="fl srch"]')
    for item in items:
      try: year = RE_YEAR_IN_NAME.search(HTML.StringFromElement(item)).group(1)
      except: year = None
      node= item.xpath('a')[0]
      title = "".join(node.xpath('descendant-or-self::text()'))
      url = node.get('href')
      id_ptn = RE_TV_ID if cate == 'tv' else RE_MOVIE_ID
      id = id_ptn.search(url).group(1)

      if year == media.year:
        score = 95
      elif len(items) == 1:
        score = 80
      else:
        score = 10
      Log.Debug('ID=%s, media_name=%s, title=%s, year=%s' %(id, media_name, title, year))
      results.Append(MetadataSearchResult(id=id, name=title, year=year, score=score, lang=lang))

def updateDaumMovie(cate, metadata):
  # (1) from detail page
  url_tmpl = DAUM_TV_DETAIL if cate == 'tv' else DAUM_MOVIE_DETAIL
  data = JSON.ObjectFromURL(url=url_tmpl % metadata.id)
  info = data['data']
  metadata.title = info['titleKo']
  metadata.original_title = info['titleEn']
  metadata.genres.clear()
  if cate == 'tv':
    try: metadata.rating = float(info['tvProgramPoint']['pointAvg'])
    except: pass
    metadata.genres.add(info['categoryHigh']['codeName'])
    metadata.studio = info['channel']['titleKo'] if info['channel'] else ''
    metadata.duration = 0
    try: metadata.originally_available_at = Datetime.ParseDate(info['startDate']).date()
    except: pass
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(info['introduce']).strip())
  else:
    metadata.year = int(info['prodYear'])
    try: metadata.rating = float(info['moviePoint']['inspectPointAvg'])
    except: pass
    for item in info['genres']:
      metadata.genres.add(item['genreName'])
    try: metadata.duration = int(info['showtime'])*60
    except: pass
    try: metadata.originally_available_at = Datetime.ParseDate(info['releaseDate']).date()
    except: pass
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(info['plot']).strip())

    metadata.countries.clear()
    for item in info['countries']:
      metadata.countries.add(item['countryKo'])

  poster_url = info['photo']['fullname']

  # (2) cast crew
  directors = list()
  writers = list()
  metadata.roles.clear()
  url_tmpl = DAUM_TV_CAST if cate == 'tv' else DAUM_MOVIE_CAST
  data = JSON.ObjectFromURL(url=url_tmpl % metadata.id)
  for item in data['data']:
    cast = item['castcrew']
    if cast['castcrewCastName'] == [u'감독', u'연출']:
      directors.append(item['nameKo'] if item['nameKo'] else item['nameEn'])
    elif cast['castcrewCastName'] == u'극본':
      writers.append(item['nameKo'] if item['nameKo'] else item['nameEn'])
    elif cast['castcrewCastName'] in [u'주연', u'조연', u'출현', u'진행']:
      role = metadata.roles.new()
      role.role = cast['castcrewTitleKo']
      role.actor = item['nameKo'] if item['nameKo'] else item['nameEn']
      metadata.roles.add(role)
  if cate == 'movie':
    metadata.directors.clear()
    metadata.writers.clear()
    for name in directors:
      metadata.directors.append(name)
    for name in writers:
      metadata.writers.append(name)

  # (3) from photo page
  url_tmpl = DAUM_TV_PHOTO if cate == 'tv' else DAUM_MOVIE_PHOTO
  data = JSON.ObjectFromURL(url=url_tmpl % metadata.id)
  max_poster = int(Prefs['max_num_posters'])
  max_art = int(Prefs['max_num_arts'])
  idx_poster = 0
  idx_art = 0
  for item in data['data']:
    if item['photoCategory'] == '1' and idx_poster < max_poster:
      art_url = item['fullname']
      if not art_url: continue
      #art_url = RE_PHOTO_SIZE.sub("/image/", art_url)
      art = HTTP.Request( item['thumbnail'] )
      idx_poster += 1
      metadata.posters[art_url] = Proxy.Preview(art, sort_order = idx_poster)
    elif item['photoCategory'] in ['2', '50'] and idx_art < max_art:
      art_url = item['fullname']
      if not art_url: continue
      #art_url = RE_PHOTO_SIZE.sub("/image/", art_url)
      art = HTTP.Request( item['thumbnail'] )
      idx_art += 1
      metadata.art[art_url] = Proxy.Preview(art, sort_order = idx_art)
  Log.Debug('Total %d posters, %d artworks' %(idx_poster, idx_art))
  if idx_poster == 0:
    poster = HTTP.Request( poster_url )
    metadata.posters[poster_url] = Proxy.Media(poster)

  if cate == 'tv':
    # (4) from episode page
    page = HTTP.Request(DAUM_TV_EPISODE % metadata.id).content
    match = Regex('MoreView\.init\(\d+, (.*), \$\(', Regex.DOTALL).search(page)
    if match:
      data = JSON.ObjectFromString(match.group(1))
      for item in data:
        episode_num = item['sequence']
        episode = metadata.seasons['1'].episodes[episode_num]
        episode.title = item['title']
        episode.summary = item['introduceDescription'].strip()
        if item['channels'][0]['broadcastDate']:
          episode.originally_available_at = Datetime.ParseDate(item['channels'][0]['broadcastDate'], '%Y%m%d').date()
        try: episode.rating = float(item['rate'])
        except: pass
        episode.directors.clear()
        episode.writers.clear()
        for name in directors:
          episode.directors.add(name)
        for name in writers:
          episode.writers.add(name)
        #episode.thumbs[thumb_url] = Proxy.Preview(thumb_data)

    # (5) fill missing info
    if Prefs['override_tv_id'] != 'None':
      page = HTTP.Request(DAUM_TV_DETAIL2 % metadata.id).content
      match = Regex('<em class="title_AKA"> *<span class="eng">([^<]*)</span>').search(page)
      if match:
        metadata.original_title = match.group(1).strip()

####################################################################################################
class DaumMovieAgent(Agent.Movies):
  name = "Daum Movie"
  languages = [Locale.Language.Korean]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual=False):
    return searchDaumMovie('movie', results, media, lang)

  def update(self, metadata, media, lang):
    Log.Info("in update ID = %s" % metadata.id)
    updateDaumMovie('movie', metadata)

    # override metadata ID
    if Prefs['override_movie_id'] != 'None':
      title = metadata.original_title if metadata.original_title else metadata.title
      if Prefs['override_movie_id'] == 'IMDB':
        url = IMDB_TITLE_SRCH % urllib.quote_plus("%s %d" % (title.encode('utf-8'), metadata.year))
        page = HTTP.Request( url ).content
        match = RE_IMDB_ID.search(page)
        if match:
          metadata.id = match.group(1)
          Log.Info("override with IMDB ID, %s" % metadata.id)

class DaumMovieTvAgent(Agent.TV_Shows):
  name = "Daum Movie"
  primary_provider = True
  languages = [Locale.Language.Korean]
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual=False):   
    return searchDaumMovie('tv', results, media, lang)

  def update(self, metadata, media, lang):
    Log.Info("in update ID = %s" % metadata.id)
    updateDaumMovie('tv', metadata)

    # override metadata ID
    if Prefs['override_tv_id'] != 'None':
      title = metadata.original_title if metadata.original_title else metadata.title
      if Prefs['override_tv_id'] == 'TVDB':
        url = TVDB_TITLE_SRCH % urllib.quote_plus(title.encode('utf-8'))
        xml = XML.ElementFromURL( url )
        node = xml.xpath('/Data/Series/seriesid')
        if node:
          metadata.id = node[0].text
          Log.Info("override with TVDB ID, %s" % metadata.id)
