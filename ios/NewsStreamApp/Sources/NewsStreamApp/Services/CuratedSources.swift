import Foundation

public struct VettedFeed: Sendable {
    public let name: String
    public let url: String
    public let category: String
    public let domain: String
    public let tier: Int
    
    public init(name: String, url: String, category: String, domain: String, tier: Int = 1) {
        self.name = name
        self.url = url
        self.category = category
        self.domain = domain
        self.tier = tier
    }
}

public enum CuratedSources {
    public static let feeds: [VettedFeed] = [
        // Tech & Science
        VettedFeed(name: "TechCrunch", url: "https://techcrunch.com/feed/", category: "Tech & Science", domain: "techcrunch.com"),
        VettedFeed(name: "The Verge", url: "https://www.theverge.com/rss/index.xml", category: "Tech & Science", domain: "theverge.com"),
        VettedFeed(name: "Ars Technica", url: "https://feeds.arstechnica.com/arstechnica/index", category: "Tech & Science", domain: "arstechnica.com"),
        VettedFeed(name: "Wired", url: "https://www.wired.com/feed/rss", category: "Tech & Science", domain: "wired.com"),
        VettedFeed(name: "Hacker News", url: "https://news.ycombinator.com/rss", category: "Tech & Science", domain: "news.ycombinator.com"),
        VettedFeed(name: "MIT Technology Review", url: "https://www.technologyreview.com/feed/", category: "Tech & Science", domain: "technologyreview.com"),
        VettedFeed(name: "Nature", url: "https://www.nature.com/nature.rss", category: "Tech & Science", domain: "nature.com"),
        VettedFeed(name: "Futura Sciences", url: "https://www.futura-sciences.com/rss/actualites.xml", category: "Tech & Science", domain: "futura-sciences.com"),
        
        // Politique & Monde
        VettedFeed(name: "Le Monde", url: "https://www.lemonde.fr/rss/une.xml", category: "Politique & Monde", domain: "lemonde.fr"),
        VettedFeed(name: "BBC World", url: "https://feeds.bbci.co.uk/news/world/rss.xml", category: "Politique & Monde", domain: "bbc.com"),
        VettedFeed(name: "France 24", url: "https://www.france24.com/fr/rss", category: "Politique & Monde", domain: "france24.com"),
        VettedFeed(name: "Courrier International", url: "https://www.courrierinternational.com/feed/all/rss.xml", category: "Politique & Monde", domain: "courrierinternational.com"),
        VettedFeed(name: "The Guardian", url: "https://www.theguardian.com/world/rss", category: "Politique & Monde", domain: "theguardian.com"),
        VettedFeed(name: "Le Figaro", url: "https://www.lefigaro.fr/rss/figaro_actualites.xml", category: "Politique & Monde", domain: "lefigaro.fr"),
        
        // Économie & Finance
        VettedFeed(name: "Les Échos", url: "https://news.google.com/rss/search?q=site:lesechos.fr+economie+when:24h&hl=fr-FR&gl=FR&ceid=FR:fr", category: "Économie & Finance", domain: "lesechos.fr"),
        VettedFeed(name: "Financial Times", url: "https://news.google.com/rss/search?q=site:ft.com+when:24h&hl=en-US&gl=US&ceid=US:en", category: "Économie & Finance", domain: "ft.com"),
        VettedFeed(name: "La Tribune", url: "https://www.latribune.fr/rss/rubriques/economie.xml", category: "Économie & Finance", domain: "latribune.fr"),
        VettedFeed(name: "Bloomberg Tech", url: "https://feeds.bloomberg.com/technology/news.rss", category: "Économie & Finance", domain: "bloomberg.com"),
        VettedFeed(name: "Zone Bourse", url: "https://www.zonebourse.com/rss/Actualites_Bourse.xml", category: "Économie & Finance", domain: "zonebourse.com"),
        
        // Climat & Environnement
        VettedFeed(name: "Reporterre", url: "https://reporterre.net/spip.php?page=backend", category: "Climat & Environnement", domain: "reporterre.net"),
        VettedFeed(name: "Actu Environnement", url: "https://news.google.com/rss/search?q=environnement+climat+when:24h&hl=fr-FR&gl=FR&ceid=FR:fr", category: "Climat & Environnement", domain: "actu-environnement.com"),
        
        // Cybersécurité & IA
        VettedFeed(name: "BleepingComputer", url: "https://www.bleepingcomputer.com/feed/", category: "Tech & Science", domain: "bleepingcomputer.com"),
        VettedFeed(name: "The Hacker News", url: "https://feeds.feedburner.com/TheHackersNews", category: "Tech & Science", domain: "thehackernews.com"),
        VettedFeed(name: "Zataz", url: "https://www.zataz.com/feed/", category: "Tech & Science", domain: "zataz.com"),
        
        // Manga & Anime (Idée 5)
        VettedFeed(name: "Anime News Network", url: "https://www.animenewsnetwork.com/all/rss.xml", category: "Manga & Anime", domain: "animenewsnetwork.com"),
        VettedFeed(name: "Manga-News FR", url: "https://www.manga-news.com/index.php/rss", category: "Manga & Anime", domain: "manga-news.com"),
        VettedFeed(name: "MyAnimeList News", url: "https://myanimelist.net/rss/news.xml", category: "Manga & Anime", domain: "myanimelist.net"),
        VettedFeed(name: "Crunchyroll News", url: "https://news.google.com/rss/search?q=site:crunchyroll.com+news+when:24h&hl=fr-FR&gl=FR&ceid=FR:fr", category: "Manga & Anime", domain: "crunchyroll.com"),

        // Jeux Vidéo & Gaming (Idée 6)
        VettedFeed(name: "IGN", url: "https://feeds.feedburner.com/ign/all", category: "Jeux Vidéo", domain: "ign.com"),
        VettedFeed(name: "Kotaku", url: "https://kotaku.com/rss", category: "Jeux Vidéo", domain: "kotaku.com"),
        VettedFeed(name: "Eurogamer", url: "https://www.eurogamer.net/feed", category: "Jeux Vidéo", domain: "eurogamer.net"),
        VettedFeed(name: "JeuxVideo.com", url: "https://news.google.com/rss/search?q=site:jeuxvideo.com+news+when:24h&hl=fr-FR&gl=FR&ceid=FR:fr", category: "Jeux Vidéo", domain: "jeuxvideo.com"),
        VettedFeed(name: "PC Gamer", url: "https://www.pcgamer.com/rss", category: "Jeux Vidéo", domain: "pcgamer.com")
    ]
}
