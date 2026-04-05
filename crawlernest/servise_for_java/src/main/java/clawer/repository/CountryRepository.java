package clawer.repository;

import clawer.model.Country;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CountryRepository extends JpaRepository<Country, Long> {
    boolean existsByCountryNameIgnoreCase(String countryName);

    boolean existsByCountryCodeIgnoreCase(String countryCode);

    boolean existsByCountryNameIgnoreCaseAndRegionNameIgnoreCase(String countryName, String regionName);

    boolean existsByCountryCodeIgnoreCaseAndRegionNameIgnoreCase(String countryCode, String regionName);

    Optional<Country> findByCountryNameIgnoreCase(String countryName);

    Optional<Country> findByCountryCodeIgnoreCase(String countryCode);
}
