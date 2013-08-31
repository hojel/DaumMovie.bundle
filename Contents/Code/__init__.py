# -*- coding: utf-8 -*-
# Daum Movie

import urllib, unicodedata, re

DAUM_MOVIE_SRCH   = "http://movie.daum.net/search.do?type=movie&q=%s"
DAUM_MOVIE_DETAIL = "http://m.movie.daum.net/data/movie/movie_info/detail.json?movieId=%s"
DAUM_MOVIE_CAST   = "http://m.movie.daum.net/data/movie/movie_info/cast_crew.json?pageNo=1&pageSize=100&movieId=%s"
DAUM_MOVIE_PHOTO  = "http://m.movie.daum.net/data/movie/photo/movie/list.json?pageNo=1&pageSize=100&id=%s"

####################################################################################################
def Start():
  HTTP.CacheTime = CACHE_1WEEK
  HTTP.Headers['Accept'] = 'text/html, application/json'

####################################################################################################
class DaumMovieAgent(Agent.Movies):
  name = "Daum Movie"
  languages = [Locale.Language.Korean]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang, manual=False):
    media_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()
    Log.Debug("search: %s %s" %(media_name, media.year))

    url = DAUM_MOVIE_SRCH % (urllib.quote(media_name.encode('utf8')))
    html = HTML.ElementFromURL( url )

    items = html.xpath('//span[@class="fl srch"]')
    for item in items:
      try: year = re.search('\((\d+)\)', HTML.StringFromElement(item)).group(1)
      except: year = None
      node= item.xpath('a')[0]
      title = "".join(node.xpath('descendant-or-self::text()'))
      url = node.get('href')
      id = re.search("movieId=(\d+)", url).group(1)

      if year == media.year:
        score = 95
      elif len(items) == 1:
        score = 80
      else:
        score = 10
      Log.Debug('ID=%s, media_name=%s, title=%s, year=%s' %(id, media_name, title, year))
      results.Append(MetadataSearchResult(id=id, name=title, year=year, score=score, lang=lang))

  def update(self, metadata, media, lang):
    Log.Info("in update ID = %s" % metadata.id)

    # (1) from detail page
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_DETAIL % metadata.id)
    info = data['data']
    metadata.title = info['titleKo']
    metadata.original_title = info['titleEn']
    metadata.year = int(info['prodYear'])
    metadata.rating = float(info['moviePoint']['inspectPointAvg'])
    metadata.genres.clear()
    for item in info['genres']:
      metadata.genres.add(item['genreName'])
    try: metadata.duration = int(info['showtime'])*60
    except: pass
    metadata.summary = String.DecodeHTMLEntities(String.StripTags(info['plot']).strip())
    poster_url = info['photo']['fullname']
    
    # countries
    metadata.countries.clear()
    for item in info['countries']:
      metadata.countries.add(item['countryKo'])
      
    # Release Date
    try: metadata.originally_available_at = Datetime.ParseDate(info['releaseDate']).date()
    except: pass
    
    # (2) cast crew
    metadata.directors.clear()
    metadata.writers.clear()
    metadata.roles.clear()
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_CAST % metadata.id)
    for item in data['data']:
      cast = item['castcrew']
      if cast['castcrewCastName'] == u'감독':
        metadata.directors.add(item['nameKo'])
      elif cast['castcrewCastName'] == u'극본':
        metadata.writers.add(item['nameKo'])
      elif cast['castcrewCastName'] in [u'주연', u'조연']:
        role = metadata.roles.new()
        role.role = cast['castcrewTitleKo']
        role.actor = item['nameKo']
        metadata.roles.add(role)
  
    # (3) from photo page
    data = JSON.ObjectFromURL(url=DAUM_MOVIE_PHOTO % metadata.id)
    max_poster = int(Prefs['max_num_posters'])
    max_art = int(Prefs['max_num_arts'])
    idx_poster = 0
    idx_art = 0
    for item in data['data']:
      if item['photoCategory'] == '1' and idx_poster < max_poster:
        idx_poster += 1
        art_url = item['fullname']
        #art_url = re.sub("/C\d+x\d+/", "/image/", art_url)
        art = HTTP.Request( item['thumbnail'] )
        metadata.posters[art_url] = Proxy.Preview(art, sort_order = idx_poster)
      elif item['photoCategory'] == '2' and idx_art < max_art:
        idx_art += 1
        art_url = item['fullname']
        #art_url = re.sub("/C\d+x\d+/", "/image/", art_url)
        art = HTTP.Request( item['thumbnail'] )
        metadata.art[art_url] = Proxy.Preview(art, sort_order = idx_art)
    Log.Debug('Total %d posters, %d artworks' %(idx_poster, idx_art))
    if idx_poster == 0:
      poster = HTTP.Request( poster_url )
      metadata.posters[poster_url] = Proxy.Media(poster)
