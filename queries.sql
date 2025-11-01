WITH age('year', toDate(json.player.dateOfBirth), toDate(date)) AS years,
    age('month', toDate(json.player.dateOfBirth), toDate(date)) % 12 AS months
SELECT
    json.player.fullName,
    json.points,
    json.ranking,
    splitByChar('_', _file)[1] AS date,
    if(months = 0, toString(years) || 'y', toString(years) || 'y ' || toString(months) || 'm') AS age
FROM file('wta_rankings/*.jsonl', JSONAsObject)
WHERE json.player.fullName LIKE '%Stojsav%' OR json.player.fullName LIKE '%Klug%' OR json.player.fullName LIKE '%Mingge Xu'
ORDER BY date, json.player.fullName::String ASC;

-- side by side

 SELECT
    age_years,
    age_months,
    concat(toString(age_years), 'y', if(age_months = 0, '', concat(' ', toString(age_months), 'm'))) AS age_display,
    -- Klugman data
    minIfOrNull(ranking::UInt16, player_name LIKE '%Klug%') AS klugman_ranking,
    -- Stojsavljevic data
    minIfOrNull(ranking::UInt16, player_name LIKE '%Stojsav%') AS stojsavljevic_ranking,
    -- Xu data
    minIfOrNull(ranking::UInt16, player_name LIKE '%Mingge%') AS xu_ranking
FROM (
    SELECT
        json.player.fullName AS player_name,
        json.points AS points,
        json.ranking AS ranking,
        age('year', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) AS age_years,
        age('month', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) % 12 AS age_months
    FROM file('wta_rankings/*.jsonl', JSONAsObject)
    WHERE (json.player.fullName LIKE '%Stojsav%')
       OR (json.player.fullName LIKE '%Klug%')
       OR (json.player.fullName LIKE '%Mingge Xu%')
)
GROUP BY age_years, age_months
HAVING klugman_ranking IS NOT NULL OR stojsavljevic_ranking IS NOT NULL OR xu_ranking IS NOT NULL
ORDER BY age_years ASC, age_months ASC;

-- jovic + andreeva

 SELECT
    age_years,
    age_months,
    concat(toString(age_years), 'y', if(age_months = 0, '', concat(' ', toString(age_months), 'm'))) AS age_display,
    minIfOrNull(ranking::UInt16, player_name LIKE '%Klug%') AS klugman_ranking,
    minIfOrNull(ranking::UInt16, player_name LIKE '%Stojsav%') AS stojsavljevic_ranking,    
    minIfOrNull(ranking::UInt16, player_name LIKE '%Mingge%') AS xu_ranking,
    minIfOrNull(ranking::UInt16, player_name LIKE 'Mirra Andreeva') AS andreeva_ranking,
    minIfOrNull(ranking::UInt16, player_name LIKE 'Iva Jovic') AS jovic_ranking
FROM (
    SELECT
        json.player.fullName AS player_name,
        json.points AS points,
        json.ranking AS ranking,
        age('year', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) AS age_years,
        age('month', toDate(json.player.dateOfBirth), toDate(splitByChar('_', _file)[1])) % 12 AS age_months
    FROM file('wta_rankings/*.jsonl', JSONAsObject)
    WHERE (json.player.fullName LIKE '%Stojsav%')
       OR (json.player.fullName LIKE '%Klug%')
       OR (json.player.fullName LIKE '%Mingge Xu%') OR (json.player.fullName LIKE 'Mirra Andreeva') OR (json.player.fullName LIKE 'Iva Jovic')
)
GROUP BY age_years, age_months
HAVING isNotNull(arrayFirstOrNull(x -> isNotNull(x), [klugman_ranking, stojsavljevic_ranking, xu_ranking, andreeva_ranking, jovic_ranking]))
ORDER BY age_years ASC, age_months ASC;