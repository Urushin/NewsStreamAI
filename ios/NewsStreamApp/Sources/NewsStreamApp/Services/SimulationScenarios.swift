import Foundation

public struct SimulationScenario: Sendable {
    public let id: String
    public let topic: String
    public let category: String
    public let articles: [RawArticle]
}

public final class SimulationScenarios: Sendable {
    public static let shared = SimulationScenarios()
    
    private init() {}
    
    public func getRotatingBatch() -> [RawArticle] {
        let allSets: [[RawArticle]] = [
            // Batch A : IA Open-Source & Puces
            [
                RawArticle(
                    title: "Meta dévoile Llama 4 : un modèle de 400 milliards de paramètres avec raisonnement natif",
                    url: "https://techcrunch.com/llama4-\(UUID().uuidString.prefix(6))",
                    content: "Meta publie Llama 4 en open-weights avec 1 million de tokens de contexte, rivalisant avec les modèles propriétaires.",
                    sourceName: "TechCrunch",
                    domain: "techcrunch.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Llama 4 : Meta accélère la course à l'IA ouverte et bouscule le marché mondial",
                    url: "https://reuters.com/llama4-\(UUID().uuidString.prefix(6))",
                    content: "L'annonce de Meta met sous pression les acteurs de l'IA commerciale en démocratisant la puissance de calcul.",
                    sourceName: "Reuters",
                    domain: "reuters.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Avec Llama 4, l'intelligence artificielle open source franchit un cap historique",
                    url: "https://lemonde.fr/llama4-\(UUID().uuidString.prefix(6))",
                    content: "Les benchmarks confirment que le nouveau modèle égale les systèmes commerciaux sur le code et les mathématiques.",
                    sourceName: "Le Monde",
                    domain: "lemonde.fr",
                    category: "Tech & Science",
                    publishedAt: Date()
                )
            ],
            // Batch B : Manga & Anime
            [
                RawArticle(
                    title: "One Piece : Eiichiro Oda et le Shonen Jump confirment les révélations sur le Siècle Oublié",
                    url: "https://animenewsnetwork.com/op-void-\(UUID().uuidString.prefix(6))",
                    content: "L'auteur annonce que les prochains chapitres lèveront le voile sur Joy Boy et les Armes Antiques.",
                    sourceName: "Anime News Network",
                    domain: "animenewsnetwork.com",
                    category: "Manga & Anime",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "One Piece entre dans sa phase culminante : planning spécial et chapitres étendus",
                    url: "https://manga-news.com/op-climax-\(UUID().uuidString.prefix(6))",
                    content: "La Shueisha annonce un rythme de parution soutenu pour marquer le dénouement de la saga.",
                    sourceName: "Manga-News",
                    domain: "manga-news.com",
                    category: "Manga & Anime",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Hunter x Hunter : Yoshihiro Togashi confirme l'achèvement de 20 nouveaux chapitres",
                    url: "https://animenewsnetwork.com/hxh-\(UUID().uuidString.prefix(6))",
                    content: "L'auteur partage les manuscrits finalisés du Continent Caché et programme la reprise.",
                    sourceName: "Anime News Network",
                    domain: "animenewsnetwork.com",
                    category: "Manga & Anime",
                    publishedAt: Date()
                )
            ],
            // Batch C : Gaming & Consoles
            [
                RawArticle(
                    title: "Nintendo officialise la Switch 2 : écran OLED 120Hz, compatibilité totale et Mario 3D",
                    url: "https://ign.com/switch2-\(UUID().uuidString.prefix(6))",
                    content: "Nintendo confirme le successeur de sa console hybride avec processeur Nvidia custom et DLSS 3.5.",
                    sourceName: "IGN",
                    domain: "ign.com",
                    category: "Jeux Vidéo & Esport",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Nintendo Switch 2 : prix, date de sortie et catalogue de lancement officialisés",
                    url: "https://jeuxvideo.com/switch2-\(UUID().uuidString.prefix(6))",
                    content: "La console sortira fin 2026 au tarif de 449€ avec une dizaine de titres exclusifs majeurs.",
                    sourceName: "Jeuxvideo.com",
                    domain: "jeuxvideo.com",
                    category: "Jeux Vidéo & Esport",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Rockstar Games dévoile de nouvelles séquences multijoueur inédites pour GTA VI",
                    url: "https://gamekult.com/gta6-\(UUID().uuidString.prefix(6))",
                    content: "Analyse des innovations techniques majeures de gestion de foule et météo volumétrique.",
                    sourceName: "Gamekult",
                    domain: "gamekult.com",
                    category: "Jeux Vidéo & Esport",
                    publishedAt: Date()
                )
            ],
            // Batch D : Espace & Sciences
            [
                RawArticle(
                    title: "Le télescope James Webb identifie des signatures atmosphériques compatibles avec la vie sur LHS 1140 b",
                    url: "https://nature.com/jwst-lhs-\(UUID().uuidString.prefix(6))",
                    content: "Détection de concentrations anormales de vapeur d'eau et de sulfure de diméthyle sur une super-Terre tempérée.",
                    sourceName: "Nature",
                    domain: "nature.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "James Webb finds habitable ocean atmosphere on temperate super-Earth",
                    url: "https://bbc.com/jwst-ocean-\(UUID().uuidString.prefix(6))",
                    content: "Spectroscopic measurements confirm dense, stable nitrogen-rich atmosphere on LHS 1140 b.",
                    sourceName: "BBC News",
                    domain: "bbc.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "SpaceX réussit le premier transfert de méthane cryogénique entre deux Starship en orbite",
                    url: "https://arstechnica.com/starship-refuel-\(UUID().uuidString.prefix(6))",
                    content: "Le test clé pour la mission lunaire Artemis III s'est déroulé sans anomalie à 400 km d'altitude.",
                    sourceName: "Ars Technica",
                    domain: "arstechnica.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                )
            ],
            // Batch E : Climat & Énergie
            [
                RawArticle(
                    title: "Batteries tout-solide : autonomie record de 1 200 km et 8 minutes de recharge validées",
                    url: "https://lesechos.fr/solid-state-\(UUID().uuidString.prefix(6))",
                    content: "Nouvelle technologie à électrolyte céramique sans risque thermique franchissant l'industrialisation.",
                    sourceName: "Les Échos",
                    domain: "lesechos.fr",
                    category: "Climat & Environnement",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Solid-state battery breakthrough delivers 1,200 km range with non-flammable electrolyte",
                    url: "https://wired.com/solid-state-\(UUID().uuidString.prefix(6))",
                    content: "Engineers validate 2,000 charge cycles without degradation for commercial rollout in 2027.",
                    sourceName: "Wired",
                    domain: "wired.com",
                    category: "Climat & Environnement",
                    publishedAt: Date()
                ),
                RawArticle(
                    title: "Fusion nucléaire : le réacteur WEST bat le record de durée de plasma stable à 50 millions de degrés",
                    url: "https://futura-sciences.com/fusion-west-\(UUID().uuidString.prefix(6))",
                    content: "Confinement magnétique maintenu pendant plus de 20 minutes continues sans érosion des parois.",
                    sourceName: "Futura Sciences",
                    domain: "futura-sciences.com",
                    category: "Tech & Science",
                    publishedAt: Date()
                )
            ]
        ]
        
        let singles: [RawArticle] = [
            RawArticle(
                title: "Découverte d'un gisement géant d'hydrogène blanc naturel dans les Pyrénées",
                url: "https://futura-sciences.com/hydrogene-\(UUID().uuidString.prefix(6))",
                content: "Une réserve potentielle de plusieurs millions de tonnes d'hydrogène décarboné identifiée.",
                sourceName: "Futura Sciences",
                domain: "futura-sciences.com",
                category: "Climat & Environnement",
                publishedAt: Date()
            ),
            RawArticle(
                title: "Archéologie sous-marine : une cité engloutie de 7 500 ans découverte en Adriatique",
                url: "https://nationalgeographic.com/adria-\(UUID().uuidString.prefix(6))",
                content: "Des relevés 3D révèlent des structures mégalithiques bien conservées sous 20m d'eau.",
                sourceName: "National Geographic",
                domain: "nationalgeographic.com",
                category: "Culture & Savoir",
                publishedAt: Date()
            ),
            RawArticle(
                title: "Train à lévitation magnétique : record mondial de 623 km/h sur voie d'essai sous vide",
                url: "https://railwaygazette.com/maglev-\(UUID().uuidString.prefix(6))",
                content: "Confirmation de la viabilité des liaisons interurbaines ultra-rapides sans frottement.",
                sourceName: "Railway Gazette",
                domain: "railwaygazette.com",
                category: "Tech & Science",
                publishedAt: Date()
            )
        ]
        
        // Pick 2 distinct multi-source sets + 1 single signal
        var chosen: [RawArticle] = []
        let shuffledSets = allSets.shuffled()
        if let first = shuffledSets.first { chosen.append(contentsOf: first) }
        if shuffledSets.count > 1 { chosen.append(contentsOf: shuffledSets[1]) }
        if let randomSingle = singles.randomElement() { chosen.append(randomSingle) }
        
        return chosen.shuffled()
    }
}
