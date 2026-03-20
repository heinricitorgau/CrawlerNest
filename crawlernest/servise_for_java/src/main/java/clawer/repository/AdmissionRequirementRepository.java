package clawer.repository;

import clawer.model.AdmissionRequirement;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface AdmissionRequirementRepository extends JpaRepository<AdmissionRequirement, Long> {
}
